"""Interactive Brokers through IB Gateway, using ``ib_async`` (spec §2, §8).

How Jarvis's concepts map onto IBKR:
- ``client_order_id`` travels in the order's ``orderRef``; a bracket's stop and target get
  ``<id>.stop`` and ``<id>.tp``. Idempotency: before placing, existing orders (including
  completed ones, which ib_async loads at connect) are searched for the same ``orderRef``.
- Brackets are a DAY limit parent with GTC children that IBKR activates as the parent
  fills and cancels together (one-cancels-other).
- Day entries that expire unfilled show up as cancelled at IBKR.
- Orders and fills without an ``orderRef`` were not made by Jarvis; they are reported with
  an ``ibkr-<permId>`` id so reconciliation flags them.
- Fills are read from ib_async's own fill store (``ib.fills()``), which is keyed by execId
  and receives the commission when IBKR sends it; ``reqExecutions`` only refreshes that
  store (its own return values carry empty commission reports). A fill is reported once its
  commission is known, so the cost is never booked as zero. A corrected execution
  (``….01`` → ``….02``) replaces the earlier version under the same base id.
- Orders loaded from earlier sessions carry their fill in ``order.filledQuantity`` only.
- ``ValidationError`` is a *warning* on a live order (e.g. code 399, "not placed until the
  market opens" after a stop is moved out of hours), not a rejection.

Every call has a timeout. A lost or slow connection raises ``BrokerUnavailableError``; a
refusal (unknown order, bad price, unknown contract) raises ``BrokerError``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, TypeVar

from ib_async import Contract, LimitOrder, Order, Stock, StopOrder, Trade
from ib_async import Fill as IbFill

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
from jarvis.domain.ticks import on_tick

T = TypeVar("T")

_ACTIVE_UNFILLED = {
    "PendingSubmit",
    "ApiPending",
    "PreSubmitted",
    "Submitted",
    "ApiUpdate",
    "PendingCancel",
    "ValidationError",
}
_CANCELLED = {"Cancelled", "ApiCancelled"}
_REJECTED = {"Inactive"}
_UNSET = 1e300  # ib_async marks unset doubles with a huge sentinel
_SETTLING = {"PendingSubmit", "ApiPending", "PendingCancel"}


class IbClient(Protocol):
    """The part of ``ib_async.IB`` Jarvis uses (lets tests supply a fake)."""

    client: Any

    def connectAsync(  # noqa: N802 - ib_async's name
        self,
        host: str,
        port: int,
        *,
        clientId: int,  # noqa: N803
        timeout: float | None,
        account: str,
        raiseSyncErrors: bool,  # noqa: N803
    ) -> Awaitable[Any]: ...

    def disconnect(self) -> Any: ...

    def fills(self) -> list[IbFill]: ...

    def reqMarketDataType(self, marketDataType: int) -> None: ...  # noqa: N802,N803

    def isConnected(self) -> bool: ...  # noqa: N802

    def accountSummaryAsync(self, account: str) -> Awaitable[list[Any]]: ...  # noqa: N802

    def positions(self, account: str) -> list[Any]: ...

    def openTrades(self) -> list[Trade]: ...  # noqa: N802

    def trades(self) -> list[Trade]: ...

    def placeOrder(self, contract: Contract, order: Order) -> Trade: ...  # noqa: N802

    def cancelOrder(self, order: Order) -> Any: ...  # noqa: N802

    def reqExecutionsAsync(self, execFilter: Any = None) -> Awaitable[list[IbFill]]: ...  # noqa: N802,N803

    def qualifyContractsAsync(self, *contracts: Contract) -> Awaitable[list[Any]]: ...  # noqa: N802


@dataclass(frozen=True, slots=True)
class IbkrSettings:
    """Where the gateway is and which account to trade. Never contains a password: the
    gateway logs in itself (IBC), Jarvis only talks to it on the internal network."""

    host: str
    port: int
    client_id: int
    account: str
    base_currency: str = "SEK"
    timeout_seconds: float = 10.0
    settle_seconds: float = 5.0


class IbkrBroker:
    def __init__(
        self,
        ib: IbClient,
        settings: IbkrSettings,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._ib = ib
        self._s = settings
        self._sleep = sleep

    # -- plumbing ------------------------------------------------------------------------

    async def _wait(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        try:
            return await asyncio.wait_for(awaitable, timeout or self._s.timeout_seconds)
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise BrokerUnavailableError(f"IBKR did not answer: {exc!r}") from exc

    def _guard(self) -> None:
        if not self._ib.isConnected():
            raise BrokerUnavailableError("not connected to IB Gateway")

    async def _settle(self, trade: Trade, until: Callable[[Trade], bool]) -> None:
        """Give IBKR a moment to acknowledge; the next sync picks up anything later."""
        waited = 0.0
        while not until(trade) and waited < self._s.settle_seconds:
            await self._sleep(0.1)
            waited += 0.1

    # -- connection --------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect and load positions, open and completed orders and today's executions.
        Each startup request has its own timeout; an incomplete load is a failed connect
        (``raiseSyncErrors``), because order idempotency depends on knowing every order."""
        if self._ib.isConnected():
            return
        await self._wait(
            self._ib.connectAsync(
                self._s.host,
                self._s.port,
                clientId=self._s.client_id,
                timeout=self._s.timeout_seconds,
                account=self._s.account,
                raiseSyncErrors=True,
            ),
            timeout=self._s.timeout_seconds * 8,
        )
        self._ib.reqMarketDataType(1)  # live only: no silent fallback to delayed quotes

    async def disconnect(self) -> None:
        self._ib.disconnect()

    def is_connected(self) -> bool:
        return self._ib.isConnected()

    # -- account -------------------------------------------------------------------------

    async def account(self) -> Account:
        self._guard()
        values = await self._wait(self._ib.accountSummaryAsync(self._s.account))
        found: dict[str, Decimal] = {}
        for value in values:
            if value.currency == self._s.base_currency and value.tag in (
                "NetLiquidation",
                "TotalCashValue",
            ):
                found[value.tag] = Decimal(value.value)
        if len(found) != 2:
            raise BrokerError("account summary is missing NetLiquidation or TotalCashValue")
        return Account(net_liquidation=found["NetLiquidation"], cash=found["TotalCashValue"])

    async def positions(self) -> tuple[BrokerPosition, ...]:
        self._guard()
        held = [
            BrokerPosition(
                symbol=p.contract.symbol,
                quantity=_whole(p.position),
                average_cost=_dec(p.avgCost),
            )
            for p in self._ib.positions(self._s.account)
            if p.position
        ]
        return tuple(sorted(held, key=lambda p: p.symbol))

    # -- orders --------------------------------------------------------------------------

    async def open_orders(self) -> tuple[BrokerOrder, ...]:
        self._guard()
        return tuple(_view(t) for t in self._ib.openTrades())

    def _find(self, client_order_id: str) -> Trade | None:
        matches = [t for t in self._ib.trades() if _ref(t.order) == client_order_id]
        return matches[-1] if matches else None

    async def order(self, client_order_id: str) -> BrokerOrder | None:
        self._guard()
        trade = self._find(client_order_id)
        return _view(trade) if trade is not None else None

    async def submit(self, request: OrderRequest) -> BrokerOrder:
        self._guard()
        existing = self._find(request.client_order_id)
        if existing is not None:
            if request.stop_price is not None and self._find(request.stop_order_id) is None:
                raise BrokerError(
                    f"bracket {request.client_order_id} exists without its stop; not resent"
                )
            view = _view(existing)
            if (view.symbol, view.side, view.quantity, view.limit_price) != (
                request.instrument.symbol,
                request.side,
                request.quantity,
                request.limit_price,
            ):
                raise DuplicateOrderIdError(request.client_order_id)
            return view
        prices = [request.limit_price, request.stop_price, request.take_profit_price]
        if not all(on_tick(p) for p in prices if p is not None):
            raise BrokerError("price is not on a valid tick")

        contract = Stock(request.instrument.symbol, "SMART", request.instrument.currency)
        qualified = await self._wait(self._ib.qualifyContractsAsync(contract))
        if not qualified or qualified[0] is None:
            raise BrokerError(f"IBKR does not know {request.instrument.symbol}")
        contract = qualified[0]

        action = "BUY" if request.side is Side.BUY else "SELL"
        try:
            ids = [self._ib.client.getReqId() for _ in range(3)]
        except (ConnectionError, OSError) as exc:
            raise BrokerUnavailableError(f"connection lost: {exc!r}") from exc
        parent = LimitOrder(
            action,
            request.quantity,
            float(request.limit_price),
            orderId=ids[0],
            orderRef=request.client_order_id,
            tif="DAY",
            account=self._s.account,
            transmit=request.stop_price is None,
        )
        orders: list[Order] = [parent]
        if request.take_profit_price is not None:
            orders.append(
                LimitOrder(
                    "SELL",
                    request.quantity,
                    float(request.take_profit_price),
                    orderId=ids[1],
                    parentId=parent.orderId,
                    orderRef=request.take_profit_order_id,
                    tif="GTC",
                    account=self._s.account,
                    transmit=False,
                )
            )
        if request.stop_price is not None:
            orders.append(
                StopOrder(
                    "SELL",
                    request.quantity,
                    float(request.stop_price),
                    orderId=ids[2],
                    parentId=parent.orderId,
                    orderRef=request.stop_order_id,
                    tif="GTC",
                    account=self._s.account,
                    transmit=True,  # the last child sends the whole bracket
                )
            )
        try:
            trades = [self._ib.placeOrder(contract, order) for order in orders]
        except (ConnectionError, OSError) as exc:
            raise BrokerUnavailableError(f"connection lost while placing: {exc!r}") from exc
        await self._settle(trades[0], lambda t: t.orderStatus.status not in _SETTLING)
        return _view(trades[0])

    async def cancel(self, client_order_id: str) -> BrokerOrder:
        self._guard()
        trade = self._find(client_order_id)
        if trade is None:
            raise BrokerError(f"unknown order {client_order_id}")
        if not trade.isDone():
            try:
                self._ib.cancelOrder(trade.order)
            except (ConnectionError, OSError) as exc:
                raise BrokerUnavailableError(f"connection lost: {exc!r}") from exc
            await self._settle(trade, lambda t: t.isDone())
        return _view(trade)

    async def modify_stop(self, client_order_id: str, stop_price: Decimal) -> BrokerOrder:
        self._guard()
        trade = self._find(client_order_id)
        if trade is None or trade.order.orderType != "STP":
            raise BrokerError(f"no protective stop {client_order_id}")
        if trade.isDone():
            raise BrokerError(f"stop {client_order_id} is no longer working")
        if stop_price <= 0 or not on_tick(stop_price):
            raise BrokerError("stop price must be positive and on a valid tick")
        previous = trade.order.auxPrice
        trade.order.auxPrice = float(stop_price)
        try:
            self._ib.placeOrder(trade.contract, trade.order)  # same orderId: a modification
        except (ConnectionError, OSError) as exc:
            trade.order.auxPrice = previous
            raise BrokerUnavailableError(f"connection lost: {exc!r}") from exc
        await self._settle(trade, lambda t: t.orderStatus.status not in _SETTLING)
        if trade.orderStatus.status in _CANCELLED:
            # ib_async marks an order cancelled when IBKR answers a modify with an error.
            # Whether the old stop still works is unknown; reconciliation will not count
            # it, so the position shows as unprotected and trading halts with an alert.
            trade.order.auxPrice = previous
            messages = [entry.message for entry in trade.log if entry.message]
            raise BrokerError(
                f"IBKR refused the stop change: {messages[-1] if messages else 'no reason'}"
            )
        return _view(trade)

    async def fills(self, since: datetime) -> tuple[Fill, ...]:
        self._guard()
        await self._wait(self._ib.reqExecutionsAsync())  # refreshes ib.fills() below
        latest: dict[str, IbFill] = {}
        for fill in self._ib.fills():
            base = _base_exec_id(fill.execution.execId)
            known = latest.get(base)
            if known is None or fill.execution.execId > known.execution.execId:
                latest[base] = fill  # a correction (.02) replaces the original (.01)
        result = []
        for base, fill in latest.items():
            execution, report = fill.execution, fill.commissionReport
            at = _utc(execution.time)
            if not report.execId or at < since:
                continue  # commission not known yet: booked at the next sync
            result.append(
                Fill(
                    fill_id=base,
                    client_order_id=execution.orderRef or f"ibkr-{execution.permId}",
                    symbol=fill.contract.symbol,
                    side=Side.BUY if execution.side == "BOT" else Side.SELL,
                    quantity=_whole(execution.shares),
                    price=_dec(execution.price),
                    commission=_dec(report.commission),
                    at=at,
                )
            )
        return tuple(sorted(result, key=lambda f: (f.at, f.fill_id)))


def _base_exec_id(exec_id: str) -> str:
    """IBKR execIds end in a correction counter (".01", ".02", ...)."""
    head, _, tail = exec_id.rpartition(".")
    return head if head and tail.isdigit() and len(tail) == 2 else exec_id


def _utc(moment: datetime) -> datetime:
    """Execution times without a zone are UTC (assumption A20, checked on the paper account)."""
    return moment.replace(tzinfo=UTC) if moment.utcoffset() is None else moment


def _dec(value: float | Decimal | None) -> Decimal:
    if value is None:
        raise BrokerError("IBKR sent an order without a price")
    return Decimal(str(value))


def _whole(value: float | Decimal) -> int:
    quantity = Decimal(str(value))
    if quantity != quantity.to_integral_value():
        raise BrokerError(f"fractional quantity {value} is not supported")
    return int(quantity)


def _ref(order: Order) -> str:
    return order.orderRef or f"ibkr-{order.permId or order.orderId}"


def _status(trade: Trade) -> OrderStatus:
    status, filled = trade.orderStatus.status, trade.orderStatus.filled
    if status == "Filled":
        return OrderStatus.FILLED
    if status in _CANCELLED:
        return OrderStatus.CANCELLED
    if status in _REJECTED:
        return OrderStatus.REJECTED
    if status in _ACTIVE_UNFILLED:
        return OrderStatus.PARTIALLY_FILLED if filled else OrderStatus.SUBMITTED
    raise BrokerError(f"unknown IBKR order status {status!r}")


def _view(trade: Trade) -> BrokerOrder:
    order, status = trade.order, _status(trade)
    ref = _ref(order)
    filled = _whole(trade.orderStatus.filled)
    stored_fill = order.filledQuantity
    if not filled and 0 < stored_fill < _UNSET:
        filled = _whole(stored_fill)  # completed order from an earlier session
    parent = ref.rsplit(".", 1)[0] if ref.endswith((".stop", ".tp")) else None
    reason = None
    if status is OrderStatus.REJECTED:
        messages = [entry.message for entry in trade.log if entry.message]
        reason = messages[-1] if messages else "rejected by IBKR"
    return BrokerOrder(
        client_order_id=ref,
        symbol=trade.contract.symbol,
        side=Side.BUY if order.action == "BUY" else Side.SELL,
        quantity=_whole(order.totalQuantity),
        status=status,
        filled_quantity=filled,
        average_fill_price=(
            _dec(trade.orderStatus.avgFillPrice) if trade.orderStatus.avgFillPrice else None
        ),
        limit_price=_dec(order.lmtPrice) if order.orderType == "LMT" else None,
        stop_price=_dec(order.auxPrice) if order.orderType == "STP" else None,
        parent_id=parent,
        reject_reason=reason,
    )
