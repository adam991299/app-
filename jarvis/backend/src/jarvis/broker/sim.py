"""An in-memory broker for tests, replay and development (spec §2 ``SimBroker``).

It behaves like a cash account (ISK): no shorting, no buying beyond available cash, and
brackets whose stop lives at the broker. Prices arrive through ``set_price``; orders
fill at the new price when it crosses their level, so a gap through a stop fills at the
gap price, not at the stop (§7 "En stop-loss garanterar inte priset").

Known simplification: one currency. Prices and cash are in the same unit, so currency
conversion is not exercised here (the risk engine's fx handling is tested on its own).

Failure injection for chaos tests: ``go_offline``/``go_online`` (orders keep working at
the "broker" while Jarvis is disconnected) and ``fail_next_call``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from jarvis.broker.models import (
    BrokerError,
    BrokerOrder,
    BrokerPosition,
    BrokerUnavailableError,
    DuplicateOrderIdError,
    Fill,
    OrderRequest,
    OrderStatus,
)
from jarvis.domain import Account, Side


@dataclass(slots=True)
class _Order:
    """Mutable internal order. ``kind`` is entry, exit, stop or take_profit."""

    view: BrokerOrder
    kind: str
    level: Decimal  # limit price, or trigger price for stops
    active: bool  # children activate once their parent has filled something
    cost: Decimal = Decimal(0)  # accumulated quantity * price, for the average


class SimBroker:
    def __init__(
        self,
        *,
        cash: Decimal,
        clock: Callable[[], datetime],
        commission_per_share: Decimal = Decimal("0.005"),
        minimum_commission: Decimal = Decimal("1"),
        max_fill_per_price: int | None = None,
        settlement_days: int = 0,
    ) -> None:
        """``settlement_days`` > 0 makes it a cash account in which money from a sale can be
        spent on buys only after that many weekdays (exchange holidays are ignored)."""
        self._cash = cash
        self._settlement_days = settlement_days
        self._unsettled: list[tuple[date, Decimal]] = []  # (settles on, amount)
        self._clock = clock
        self._per_share = commission_per_share
        self._minimum = minimum_commission
        self._max_fill = max_fill_per_price
        self._connected = False
        self._online = True
        self._fail_next: BrokerError | None = None
        self._prices: dict[str, Decimal] = {}
        self._positions: dict[str, tuple[int, Decimal]] = {}
        self._orders: dict[str, _Order] = {}
        self._requests: dict[str, OrderRequest] = {}
        self._fills: list[Fill] = []

    # -- failure injection ---------------------------------------------------------

    def go_offline(self) -> None:
        self._online = False
        self._connected = False

    def go_online(self) -> None:
        self._online = True

    def fail_next_call(self, error: BrokerError) -> None:
        self._fail_next = error

    def _guard(self) -> None:
        if self._fail_next is not None:
            error, self._fail_next = self._fail_next, None
            raise error
        if not self._connected:
            raise BrokerUnavailableError("not connected to the broker")

    # -- BrokerAdapter ---------------------------------------------------------------

    async def connect(self) -> None:
        if not self._online:
            raise BrokerUnavailableError("broker is offline")
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def account(self) -> Account:
        self._guard()
        value = sum(
            (qty * self._prices.get(sym, cost) for sym, (qty, cost) in self._positions.items()),
            Decimal(0),
        )
        settled = self._settled_cash() if self._settlement_days else None
        return Account(net_liquidation=self._cash + value, cash=self._cash, settled_cash=settled)

    def _settled_cash(self) -> Decimal:
        today = self._clock().date()
        self._unsettled = [(day, amount) for day, amount in self._unsettled if day > today]
        return self._cash - sum((amount for _, amount in self._unsettled), Decimal(0))

    def _settles_on(self, day: date) -> date:
        left = self._settlement_days
        while left:
            day += timedelta(days=1)
            left -= day.weekday() < 5
        return day

    async def positions(self) -> tuple[BrokerPosition, ...]:
        self._guard()
        return tuple(BrokerPosition(s, q, c) for s, (q, c) in sorted(self._positions.items()))

    async def open_orders(self) -> tuple[BrokerOrder, ...]:
        self._guard()
        return tuple(o.view for o in self._orders.values() if not o.view.status.is_terminal)

    async def order(self, client_order_id: str) -> BrokerOrder | None:
        self._guard()
        found = self._orders.get(client_order_id)
        return found.view if found else None

    async def fills(self, since: datetime) -> tuple[Fill, ...]:
        self._guard()
        return tuple(f for f in self._fills if f.at >= since)

    async def submit(self, request: OrderRequest) -> BrokerOrder:
        self._guard()
        existing = self._requests.get(request.client_order_id)
        if existing is not None:
            if existing != request:
                raise DuplicateOrderIdError(request.client_order_id)
            return self._orders[request.client_order_id].view
        children = (request.stop_order_id, request.take_profit_order_id)
        if any(cid in self._orders for cid in (request.client_order_id, *children)):
            raise DuplicateOrderIdError(request.client_order_id)

        self._requests[request.client_order_id] = request
        reason = self._rejection(request)
        kind = "entry" if request.side is Side.BUY else "exit"
        self._add(request.client_order_id, request, kind, request.limit_price, active=True)
        if reason is not None:
            self._set(request.client_order_id, status=OrderStatus.REJECTED, reject_reason=reason)
            return self._orders[request.client_order_id].view
        if request.stop_price is not None:
            self._add(request.stop_order_id, request, "stop", request.stop_price, active=False)
        if request.take_profit_price is not None:
            self._add(
                request.take_profit_order_id,
                request,
                "take_profit",
                request.take_profit_price,
                active=False,
            )
        self._match(request.instrument.symbol)
        return self._orders[request.client_order_id].view

    async def cancel(self, client_order_id: str) -> BrokerOrder:
        self._guard()
        found = self._orders.get(client_order_id)
        if found is None:
            raise BrokerError(f"unknown order {client_order_id}")
        if not found.view.status.is_terminal:
            self._set(client_order_id, status=OrderStatus.CANCELLED)
            self._sync_bracket(found)
        return self._orders[client_order_id].view

    async def modify_stop(self, client_order_id: str, stop_price: Decimal) -> BrokerOrder:
        self._guard()
        found = self._orders.get(client_order_id)
        if found is None or found.kind != "stop":
            raise BrokerError(f"no protective stop {client_order_id}")
        if found.view.status.is_terminal:
            raise BrokerError(f"stop {client_order_id} is no longer working")
        if stop_price <= 0:
            raise BrokerError("stop price must be positive")
        found.level = stop_price
        self._set(client_order_id, stop_price=stop_price)
        self._match(found.view.symbol)
        return self._orders[client_order_id].view

    # -- simulation controls -----------------------------------------------------------

    def set_price(self, symbol: str, price: Decimal) -> None:
        if price <= 0:
            raise ValueError("price must be positive")
        self._prices[symbol] = price
        self._match(symbol)

    def expire_day_orders(self) -> None:
        """End of session: working entries and exits expire; stops and targets stay."""
        for cid, order in list(self._orders.items()):
            if order.kind in ("entry", "exit") and order.view.status.is_working:
                self._set(cid, status=OrderStatus.EXPIRED)
                self._sync_bracket(order)

    # -- internals ---------------------------------------------------------------------

    def _rejection(self, request: OrderRequest) -> str | None:
        symbol = request.instrument.symbol
        if request.side is Side.BUY:
            reserved = sum(
                (
                    (o.view.quantity - o.view.filled_quantity) * o.level
                    + self._commission(o.view.quantity - o.view.filled_quantity)
                    for o in self._orders.values()
                    if o.kind == "entry" and o.view.status.is_working
                ),
                Decimal(0),
            )
            needed = request.quantity * request.limit_price + self._commission(request.quantity)
            if needed > self._cash - reserved:
                return "insufficient cash (cash account, no margin)"
            if self._settlement_days and needed > self._settled_cash() - reserved:
                return "insufficient settled cash (sale proceeds have not settled)"
            return None
        held = self._positions.get(symbol, (0, Decimal(0)))[0]
        if request.quantity > held - self._working_sell_quantity(symbol):
            return "sell exceeds position (short selling not allowed)"
        if request.quantity > held - self._working_sell_quantity(symbol) - self._protected(symbol):
            return "sell overlaps shares covered by a working stop; cancel the stop first"
        return None

    def _protected(self, symbol: str) -> int:
        """Shares covered by working brackets (stop and target cover the same shares)."""
        covered = 0
        for parent in self._orders.values():
            if parent.kind != "entry" or parent.view.symbol != symbol:
                continue
            children = self._children(parent.view.client_order_id)
            if any(not c.view.status.is_terminal for c in children):
                sold = sum(c.view.filled_quantity for c in children)
                covered += parent.view.filled_quantity - sold
        return covered

    def _working_sell_quantity(self, symbol: str) -> int:
        return sum(
            o.view.quantity - o.view.filled_quantity
            for o in self._orders.values()
            if o.kind == "exit" and o.view.symbol == symbol and o.view.status.is_working
        )

    def _commission(self, quantity: int) -> Decimal:
        return max(quantity * self._per_share, self._minimum)

    def _add(self, cid: str, req: OrderRequest, kind: str, level: Decimal, *, active: bool) -> None:
        side = Side.BUY if kind == "entry" else Side.SELL
        view = BrokerOrder(
            client_order_id=cid,
            symbol=req.instrument.symbol,
            side=side,
            quantity=req.quantity,
            status=OrderStatus.SUBMITTED,
            filled_quantity=0,
            average_fill_price=None,
            limit_price=None if kind == "stop" else level,
            stop_price=level if kind == "stop" else None,
            parent_id=req.client_order_id if kind in ("stop", "take_profit") else None,
        )
        self._orders[cid] = _Order(view=view, kind=kind, level=level, active=active)

    def _set(self, cid: str, **changes: object) -> None:
        order = self._orders[cid]
        order.view = replace(order.view, **changes)  # type: ignore[arg-type]

    def _children(self, parent_id: str) -> list[_Order]:
        return [o for o in self._orders.values() if o.view.parent_id == parent_id]

    def _triggered(self, order: _Order, price: Decimal) -> bool:
        if order.kind == "entry":
            return price <= order.level
        if order.kind == "stop":
            return price <= order.level
        return price >= order.level  # exit limit and take-profit sell at or above

    def _fillable(self, order: _Order) -> int:
        """Children may only sell what their parent bought (never more than held)."""
        remaining = order.view.quantity - order.view.filled_quantity
        if order.kind in ("stop", "take_profit"):
            parent = self._orders[order.view.parent_id or ""]
            sold = sum(c.view.filled_quantity for c in self._children(parent.view.client_order_id))
            remaining = parent.view.filled_quantity - sold
        if order.view.side is Side.SELL:
            remaining = min(remaining, self._positions.get(order.view.symbol, (0, Decimal(0)))[0])
        if self._max_fill is not None:
            remaining = min(remaining, self._max_fill)
        return max(remaining, 0)

    def _match(self, symbol: str) -> None:
        price = self._prices.get(symbol)
        if price is None:
            return
        for cid in list(self._orders):
            order = self._orders[cid]
            if order.view.symbol != symbol or order.view.status.is_terminal or not order.active:
                continue
            if not self._triggered(order, price):
                continue
            quantity = self._fillable(order)
            if quantity == 0:
                continue
            self._fill(order, quantity, price)

    def _fill(self, order: _Order, quantity: int, price: Decimal) -> None:
        cid, symbol = order.view.client_order_id, order.view.symbol
        commission = self._commission(quantity)
        held, avg = self._positions.get(symbol, (0, Decimal(0)))
        if order.view.side is Side.BUY:
            self._cash -= quantity * price + commission
            new_qty = held + quantity
            self._positions[symbol] = (new_qty, (held * avg + quantity * price) / new_qty)
        else:
            self._cash += quantity * price - commission
            if self._settlement_days:
                settles = self._settles_on(self._clock().date())
                self._unsettled.append((settles, quantity * price - commission))
            if held - quantity:
                self._positions[symbol] = (held - quantity, avg)
            else:
                del self._positions[symbol]

        order.cost += quantity * price
        filled = order.view.filled_quantity + quantity
        done = filled == order.view.quantity
        self._set(
            cid,
            filled_quantity=filled,
            average_fill_price=order.cost / filled,
            status=OrderStatus.FILLED if done else OrderStatus.PARTIALLY_FILLED,
        )
        fill_id = f"sim-{len(self._fills) + 1}"
        self._fills.append(
            Fill(fill_id, cid, symbol, order.view.side, quantity, price, commission, self._clock())
        )

        if order.kind == "entry":
            for child in self._children(cid):
                child.active = True
        self._sync_bracket(order)

    def _sync_bracket(self, order: _Order) -> None:
        """Keep a bracket's stop and target in line with what the entry actually bought.

        - While the entry works, children cover its full quantity.
        - Once it is done (filled, cancelled or expired), they cover only what was filled;
          nothing filled means the children are cancelled.
        - When the children have sold everything that was bought, the bracket is closed
          and the remaining sibling is cancelled (one-cancels-other).
        """
        parent = self._orders.get(order.view.parent_id or order.view.client_order_id)
        if parent is None or parent.kind != "entry":
            return
        children = self._children(parent.view.client_order_id)
        target = (
            parent.view.quantity if parent.view.status.is_working else parent.view.filled_quantity
        )
        sold = sum(child.view.filled_quantity for child in children)
        closed = not parent.view.status.is_working and sold >= parent.view.filled_quantity
        for child in children:
            if child.view.status.is_terminal:
                continue
            if closed and child.view.filled_quantity > 0:
                filled = child.view.filled_quantity
                self._set(child.view.client_order_id, quantity=filled, status=OrderStatus.FILLED)
            elif closed:
                self._set(child.view.client_order_id, status=OrderStatus.CANCELLED)
            elif child.view.quantity != target:
                self._set(child.view.client_order_id, quantity=target)
