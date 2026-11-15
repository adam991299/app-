"""The execution engine (spec §8). One instance runs at a time and handles one request at
a time, so its view of orders cannot race with itself.

Guarantees:
- **Idempotent:** an order's id comes from its signal and is journaled *before* it is
  sent. A replayed signal is recognised and never sent twice, and the broker refuses a
  reused id.
- **Always protected:** entries go out as brackets, so the stop lives at the broker from
  the first fill. Exits in this version happen only by raising that stop, never by
  removing it, so there is no moment without protection. A stop is never lowered.
- **One instance:** nothing else may write orders for the account. Running two engines at
  once is not supported (a database lock for this is planned with the deployment, Fas 7).
- **The broker is the truth:** ``reconcile`` compares Jarvis's books with the broker every
  minute. Any mismatch, unknown order or position without a stop halts trading (risk
  state HALTED) and alerts Adam until it is resolved.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, TypeVar

from jarvis.broker import (
    BrokerAdapter,
    BrokerError,
    BrokerOrder,
    BrokerPosition,
    BrokerUnavailableError,
    DuplicateOrderIdError,
    OrderRequest,
    OrderStatus,
)
from jarvis.config.settings import Risk
from jarvis.domain import Account, Instrument, Position, Quote, Side
from jarvis.domain.ticks import round_down, round_up
from jarvis.execution.alerts import AlertLevel, Alerts
from jarvis.execution.states import InvalidTransitionError, check_transition
from jarvis.risk.breakers import BreakerStatus, Controls, SystemHealth, TradingState, evaluate
from jarvis.risk.engine import (
    MarketSession,
    OrderProposal,
    PendingOrder,
    RiskContext,
    RiskEngine,
)
from jarvis.risk.reasons import Reason
from jarvis.store.periods import day_start
from jarvis.store.repo import NewOrder, Store, StoredOrder

T = TypeVar("T")
QuoteSource = Callable[[Instrument], Awaitable[Quote | None]]
SessionSource = Callable[[Instrument, datetime], MarketSession]

logger = logging.getLogger(__name__)

_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
FILL_LOOKBACK = timedelta(days=7)


class Outcome(StrEnum):
    SUBMITTED = "submitted"
    REJECTED_BY_RISK = "rejected_by_risk"
    REJECTED_BY_BROKER = "rejected_by_broker"
    DUPLICATE = "duplicate"
    BROKER_UNAVAILABLE = "broker_unavailable"
    STOP_RAISED = "stop_raised"
    STOP_UNCHANGED = "stop_unchanged"


@dataclass(frozen=True, slots=True)
class EntrySignal:
    """A strategy's wish to open a long position. ``signal_id`` must be deterministic
    (e.g. strategy + symbol + bar date) so a replay produces the same id."""

    signal_id: str
    strategy: str
    instrument: Instrument
    quantity: int
    limit_price: Decimal
    stop_price: Decimal
    expected_edge: Decimal
    estimated_cost: Decimal
    explanation_sv: str
    take_profit_price: Decimal | None = None
    features: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Result:
    outcome: Outcome
    client_order_id: str
    reasons: tuple[Reason, ...] = ()
    detail: str | None = None


class UnknownInstrumentError(Exception):
    """The broker reports a holding Jarvis has no instrument data for."""


class ExecutionEngine:
    def __init__(
        self,
        *,
        broker: BrokerAdapter,
        store: Store,
        risk: Risk,
        instruments: Mapping[str, Instrument],
        quotes: QuoteSource,
        sessions: SessionSource,
        clock: Callable[[], datetime],
        clock_drift: Callable[[], float],
        alerts: Alerts,
        base_currency: str = "SEK",
    ) -> None:
        self._broker = broker
        self._store = store
        self._risk = risk
        self._checker = RiskEngine(risk)
        self._instruments = instruments
        self._quotes = quotes
        self._sessions = sessions
        self._clock = clock
        self._clock_drift = clock_drift
        self._alerts = alerts
        self._base_currency = base_currency
        self._broker_errors = 0
        self._reconciled = False
        self._problems: set[str] = set()  # keys found since the current reconciliation began
        self._alerted: set[str] = set()  # keys already sent to Adam and not yet resolved
        self._unsent: list[tuple[AlertLevel, str]] = []  # alerts whose delivery failed

    # -- broker calls and health ------------------------------------------------------

    async def _call(self, awaitable: Awaitable[T]) -> T:
        """Counts consecutive connection failures. A broker *refusal* (e.g. an unknown
        order) proves the connection works, so it resets the count like a success."""
        try:
            result = await awaitable
        except BrokerUnavailableError:
            self._broker_errors += 1
            raise
        except BrokerError:
            self._broker_errors = 0
            raise
        self._broker_errors = 0
        return result

    def health(self) -> SystemHealth:
        return SystemHealth(
            broker_connected=self._broker.is_connected(),
            consecutive_broker_errors=self._broker_errors,
            clock_drift_seconds=self._clock_drift(),
            positions_reconciled=self._reconciled,
        )

    async def trading_status(self, now: datetime) -> BreakerStatus:
        marks = await self._store.equity_marks(now)
        if marks is None:
            return BreakerStatus(TradingState.HALTED, (Reason.NOT_RECONCILED,), False)
        controls = await self._store.controls()
        status = evaluate(
            marks,
            self.health(),
            Controls(paused=controls.paused, kill_switch_engaged=controls.kill_switch_engaged),
            self._risk.circuit_breakers,
        )
        if status.kill_switch_should_engage:
            await self._store.engage_kill_switch("drawdown", actor="jarvis", at=now)
            await self._send(
                AlertLevel.CRITICAL,
                "Kill switch är aktiverad: kontot har fallit för mycket från toppen. "
                "Inga nya affärer tas förrän du startar handeln igen i appen.",
            )
        return status

    async def _send(self, level: AlertLevel, message_sv: str) -> bool:
        """Deliver an alert. A failed delivery never interrupts trading logic; the alert
        is kept and retried at the next reconciliation."""
        try:
            await self._alerts.send(level, message_sv)
        except Exception:
            logger.exception("alert delivery failed; will retry")
            self._unsent.append((level, message_sv))
            return False
        return True

    async def _retry_unsent(self) -> None:
        pending, self._unsent = self._unsent, []
        for level, message in pending:
            await self._send(level, message)

    async def _problem(self, key: str, message_sv: str) -> None:
        """Halt and alert. Each problem (by key) is alerted once until it is resolved, so a
        problem that persists or changes its numbers does not alert every minute."""
        self._reconciled = False
        self._problems.add(key)
        if key not in self._alerted:
            self._alerted.add(key)
            await self._send(AlertLevel.CRITICAL, message_sv)

    # -- entries --------------------------------------------------------------------------

    async def submit_entry(self, signal: EntrySignal) -> Result:
        cid = signal.signal_id
        if not _ID_PATTERN.match(cid):
            raise ValueError(f"invalid signal id {cid!r}")
        now = self._clock()
        existing = await self._store.order(cid)
        if existing is not None and existing.status is not OrderStatus.NEW:
            return Result(Outcome.DUPLICATE, cid, detail=existing.status.value)
        if existing is not None:
            # Journaled but unconfirmed: Jarvis may have died after the broker accepted it.
            try:
                at_broker = await self._call(self._broker.order(cid))
            except BrokerError as exc:
                return Result(Outcome.BROKER_UNAVAILABLE, cid, detail=str(exc))
            if at_broker is not None:
                await self._apply(at_broker, now)
                return Result(Outcome.DUPLICATE, cid, detail=at_broker.status.value)

        # Round to the broker's price ticks before anything is checked or journaled, in the
        # direction that never adds risk: pay at most the limit, stop no farther away.
        limit_price = round_down(signal.limit_price)
        stop_price = round_up(signal.stop_price)
        take_profit = (
            None if signal.take_profit_price is None else round_up(signal.take_profit_price)
        )
        proposal = OrderProposal(
            instrument=signal.instrument,
            side=Side.BUY,
            quantity=signal.quantity,
            limit_price=limit_price,
            estimated_cost=signal.estimated_cost,
            stop_price=stop_price,
            expected_edge=signal.expected_edge,
        )
        try:
            context = await self._context(now, signal.instrument)
        except BrokerError as exc:
            return Result(Outcome.BROKER_UNAVAILABLE, cid, detail=str(exc))
        except UnknownInstrumentError as exc:
            await self._problem(
                f"unknown-instrument:{exc}",
                f"Mäklaren rapporterar ett innehav jag inte känner till: {exc}.",
            )
            return Result(Outcome.REJECTED_BY_RISK, cid, (Reason.NOT_RECONCILED,))

        decision = self._checker.check(proposal, context)
        await self._store.record_risk_decision(
            at=now,
            client_order_id=cid,
            symbol=signal.instrument.symbol,
            side=Side.BUY.value,
            quantity=signal.quantity,
            approved=decision.approved,
            reasons=[r.value for r in decision.reasons],
            trading_state=context.breakers.state.value,
        )
        if not decision.approved:
            return Result(Outcome.REJECTED_BY_RISK, cid, decision.reasons)

        request = OrderRequest(
            client_order_id=cid,
            instrument=signal.instrument,
            side=Side.BUY,
            quantity=signal.quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            take_profit_price=take_profit,
        )
        await self._journal(request, signal, now)
        try:
            view = await self._call(self._broker.submit(request))
        except DuplicateOrderIdError:
            await self._problem(
                f"id-collision:{cid}", f"Mäklaren har redan en annan order med id {cid}."
            )
            return Result(Outcome.REJECTED_BY_BROKER, cid, detail="duplicate order id")
        except BrokerError as exc:
            return Result(Outcome.BROKER_UNAVAILABLE, cid, detail=str(exc))

        await self._apply(view, now)
        for child_id in _child_ids(request):
            child = await self._call(self._broker.order(child_id))
            if child is not None:
                await self._apply(child, now)
        if view.status is OrderStatus.REJECTED:
            for child_id in _child_ids(request):  # the broker never created them
                await self._store.update_order(
                    child_id,
                    at=now,
                    status=OrderStatus.CANCELLED,
                    filled_quantity=0,
                    average_fill_price=None,
                    reject_reason="entry rejected by the broker",
                )
            return Result(Outcome.REJECTED_BY_BROKER, cid, detail=view.reject_reason)
        return Result(Outcome.SUBMITTED, cid)

    async def _journal(self, request: OrderRequest, signal: EntrySignal, now: datetime) -> None:
        symbol = request.instrument.symbol
        await self._store.add_order(
            NewOrder(
                client_order_id=request.client_order_id,
                kind="entry",
                symbol=symbol,
                side=Side.BUY.value,
                quantity=request.quantity,
                limit_price=request.limit_price,
                stop_price=request.stop_price,
                strategy=signal.strategy,
                explanation_sv=signal.explanation_sv,
                currency=request.instrument.currency,
                signal={
                    "expected_edge": str(signal.expected_edge),
                    "estimated_cost": str(signal.estimated_cost),
                    **signal.features,
                },
            ),
            at=now,
        )
        children: list[tuple[str, str, Decimal | None, Decimal | None]] = [
            ("stop", request.stop_order_id, None, request.stop_price)
        ]
        if request.take_profit_price is not None:
            children.append(
                ("take_profit", request.take_profit_order_id, request.take_profit_price, None)
            )
        for kind, child_id, limit, stop in children:
            await self._store.add_order(
                NewOrder(
                    client_order_id=child_id,
                    kind=kind,
                    symbol=symbol,
                    side=Side.SELL.value,
                    quantity=request.quantity,
                    limit_price=limit,
                    stop_price=stop,
                    strategy=signal.strategy,
                    parent_id=request.client_order_id,
                    currency=request.instrument.currency,
                ),
                at=now,
            )

    # -- exits: raising the stop ------------------------------------------------------------

    async def raise_stop(self, entry_id: str, new_stop: Decimal) -> Result:
        """Move a bracket's stop up (trailing exit). Never down, never through the price."""
        stop_id = f"{entry_id}.stop"
        new_stop = round_down(new_stop)
        stored = await self._store.order(stop_id)
        if stored is None or stored.status.is_terminal:
            return Result(Outcome.STOP_UNCHANGED, stop_id, detail="no working stop")
        try:
            current = await self._call(self._broker.order(stop_id))
        except BrokerError as exc:
            return Result(Outcome.BROKER_UNAVAILABLE, stop_id, detail=str(exc))
        if current is None or current.stop_price is None or not current.status.is_working:
            return Result(Outcome.STOP_UNCHANGED, stop_id, detail="no working stop")
        if new_stop <= current.stop_price:  # the broker's level, not the journal's
            return Result(Outcome.STOP_UNCHANGED, stop_id, detail="a stop is never lowered")
        instrument = self._instruments.get(stored.symbol)
        quote = await self._quotes(instrument) if instrument is not None else None
        if quote is None or new_stop >= quote.last:
            return Result(Outcome.STOP_UNCHANGED, stop_id, detail="new stop not below the price")
        now = self._clock()
        try:
            view = await self._call(self._broker.modify_stop(stop_id, new_stop))
        except BrokerError as exc:
            return Result(Outcome.BROKER_UNAVAILABLE, stop_id, detail=str(exc))
        await self._apply(view, now)
        return Result(Outcome.STOP_RAISED, stop_id)

    # -- keeping the books in line with the broker ---------------------------------------------

    async def _apply(self, view: BrokerOrder, now: datetime) -> None:
        stored = await self._store.known_order(view.client_order_id)
        mismatch = _identity_mismatch(stored, view)
        if mismatch is not None:
            await self._problem(
                f"identity:{view.client_order_id}",
                f"Ordern {view.client_order_id} hos mäklaren är inte den jag skapade "
                f"({mismatch}). Jag pausar nya affärer tills den är utredd.",
            )
            return
        try:
            check_transition(
                stored.status,
                view.status,
                filled_before=stored.filled_quantity,
                filled_after=view.filled_quantity,
            )
        except InvalidTransitionError as exc:
            await self._problem(
                f"transition:{view.client_order_id}",
                f"Mäklarens besked om order {view.client_order_id} går inte ihop ({exc}).",
            )
            return
        if view.stop_price is not None and view.stop_price != stored.stop_price:
            await self._store.set_stop_price(view.client_order_id, view.stop_price, at=now)
        await self._store.update_order(
            view.client_order_id,
            at=now,
            status=view.status,
            filled_quantity=view.filled_quantity,
            average_fill_price=view.average_fill_price,
            quantity=view.quantity if view.quantity != stored.quantity else None,
            reject_reason=view.reject_reason,
        )

    async def sync(self) -> None:
        """Pull every open order's status and every recent fill from the broker."""
        now = self._clock()
        for stored in await self._store.open_orders():
            view = await self._call(self._broker.order(stored.client_order_id))
            if view is not None:
                await self._apply(view, now)
            elif stored.status is not OrderStatus.NEW:
                await self._problem(
                    f"missing:{stored.client_order_id}",
                    f"Ordern {stored.client_order_id} finns inte längre hos mäklaren.",
                )
        for fill in await self._call(self._broker.fills(now - FILL_LOOKBACK)):
            if await self._store.order(fill.client_order_id) is None:
                await self._problem(
                    f"foreign-fill:{fill.fill_id}",
                    f"Mäklaren rapporterar en affär i {fill.symbol} som jag inte gjort.",
                )
                continue
            await self._store.record_fill(fill)

    async def recover(self) -> bool:
        """After a start or crash: orders journaled but never sent are closed as not sent,
        then reconcile. Their signal ids are spent: the strategy's next bar produces a new
        id, which must pass risk again at the prices of that moment."""
        now = self._clock()
        for stored in await self._store.open_orders():
            if stored.status is not OrderStatus.NEW:
                continue
            try:
                at_broker = await self._call(self._broker.order(stored.client_order_id))
            except BrokerError:
                self._reconciled = False
                return False
            if at_broker is None:
                await self._store.update_order(
                    stored.client_order_id,
                    at=now,
                    status=OrderStatus.CANCELLED,
                    filled_quantity=0,
                    average_fill_price=None,
                    reject_reason="never reached the broker",
                )
        return await self.reconcile()

    async def reconcile(self) -> bool:
        """Compare books with the broker (§8). True only if everything matches and every
        position is fully covered by a working stop. Trading resumes by itself once a
        later reconciliation finds no problem; problems that are gone can alert again if
        they come back."""
        now = self._clock()
        self._problems = set()
        await self._retry_unsent()
        try:
            snapshot = await self._snapshot()
            if snapshot.booked != snapshot.actual:
                # A fill may have landed between the calls; look once more before alarming.
                snapshot = await self._snapshot()
        except BrokerError:
            self._reconciled = False
            return False
        account, orders, booked, actual = (
            snapshot.account,
            snapshot.orders,
            snapshot.booked,
            snapshot.actual,
        )
        if account.net_liquidation > 0:
            await self._store.record_equity(
                at=now, net_liquidation=account.net_liquidation, cash=account.cash
            )
        else:
            await self._problem(
                "bad-equity", "Mäklaren rapporterar ett orimligt kontovärde (noll eller negativt)."
            )

        for order in orders:
            if await self._store.order(order.client_order_id) is None:
                await self._problem(
                    f"foreign-order:{order.client_order_id}",
                    f"Mäklaren har en order som jag inte skapat ({order.client_order_id}, "
                    f"{order.symbol}). Jag pausar nya affärer tills den är utredd.",
                )
            else:
                # Also catches an order the journal believes is finished but still works.
                await self._apply(order, now)
        if booked != actual:
            await self._problem(
                "position-mismatch",
                "Mina positioner stämmer inte med mäklarens. "
                f"Jag: {_describe(booked)}. Mäklaren: {_describe(actual)}.",
            )
        unknown = sorted(s for s in actual if s not in self._instruments)
        if unknown:
            await self._problem(
                f"unknown-holding:{','.join(unknown)}",
                f"Jag saknar uppgifter om innehavet {', '.join(unknown)}.",
            )
        try:
            active = await self._active_stops(orders)
        except BrokerError:
            self._reconciled = False
            return False
        covered = active.coverage
        unprotected = sorted(s for s, q in actual.items() if covered.get(s, 0) < q)
        if unprotected:
            await self._problem(
                f"unprotected:{','.join(unprotected)}",
                f"Positionen i {', '.join(unprotected)} saknar fullt skydd av en stopporder.",
            )
        self._alerted &= self._problems
        self._reconciled = not self._problems
        await self._store.save_account_state(
            {**await self._state_payload(now, snapshot, active), "reconciled": self._reconciled},
            at=now,
        )
        return self._reconciled

    async def _state_payload(
        self, now: datetime, snapshot: _Snapshot, stops: _Stops
    ) -> dict[str, Any]:
        """What the app shows (see ``api/state.py``). Values are exact decimal strings."""
        status = await self.trading_status(now)
        strategies = await self._store.entry_strategies()
        positions = []
        for bp in snapshot.positions:
            instrument = self._instruments.get(bp.symbol)
            quote = await self._quotes(instrument) if instrument is not None else None
            entry: dict[str, Any] = {
                "symbol": bp.symbol,
                "quantity": bp.quantity,
                "currency": instrument.currency if instrument is not None else None,
                "average_price": str(bp.average_cost),
                "last_price": None,
                "market_value": None,
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
                "stop_price": _text(stops.levels.get(bp.symbol)),
                "strategy": strategies.get(bp.symbol),
            }
            if quote is not None:
                value = bp.quantity * quote.last * quote.fx_to_base
                pnl = (quote.last - bp.average_cost) * bp.quantity * quote.fx_to_base
                entry |= {
                    "last_price": str(quote.last),
                    "market_value": str(value.quantize(_CENT)),
                    "unrealized_pnl": str(pnl.quantize(_CENT)),
                    "unrealized_pnl_pct": str(
                        ((quote.last / bp.average_cost - 1) * 100).quantize(_CENT)
                    ),
                }
            positions.append(entry)
        return {
            "base_currency": self._base_currency,
            "net_liquidation": str(snapshot.account.net_liquidation),
            "cash": str(snapshot.account.cash),
            "positions": positions,
            "trading_state": status.state.value,
            "reasons": [r.value for r in status.reasons],
            "broker_connected": self._broker.is_connected(),
        }

    async def _snapshot(self) -> _Snapshot:
        await self.sync()
        account = await self._call(self._broker.account())
        positions = await self._call(self._broker.positions())
        orders = await self._call(self._broker.open_orders())
        return _Snapshot(
            account=account,
            positions=positions,
            orders=orders,
            booked=await self._store.booked_positions(),
            actual={p.symbol: p.quantity for p in positions},
        )

    async def _active_stops(self, orders: tuple[BrokerOrder, ...]) -> _Stops:
        """Protection that is real right now. A bracket's stop only protects what its entry
        has bought and its children have not yet sold; the stop of a resting, unfilled
        entry protects nothing."""
        coverage: dict[str, int] = {}
        levels: dict[str, Decimal] = {}
        for order in orders:
            if order.stop_price is None or order.side is not Side.SELL or order.parent_id is None:
                continue
            parent = await self._call(self._broker.order(order.parent_id))
            bought = parent.filled_quantity if parent is not None else 0
            sold = 0
            for sibling_id in (f"{order.parent_id}.stop", f"{order.parent_id}.tp"):
                sibling = await self._call(self._broker.order(sibling_id))
                sold += sibling.filled_quantity if sibling is not None else 0
            active = min(order.quantity - order.filled_quantity, bought - sold)
            if active <= 0:
                continue
            coverage[order.symbol] = coverage.get(order.symbol, 0) + active
            known = levels.get(order.symbol)
            levels[order.symbol] = (
                order.stop_price if known is None else min(known, order.stop_price)
            )
        return _Stops(coverage, levels)

    # -- risk context ---------------------------------------------------------------------------

    async def _context(self, now: datetime, instrument: Instrument) -> RiskContext:
        account = await self._call(self._broker.account())
        broker_positions = await self._call(self._broker.positions())
        orders = await self._call(self._broker.open_orders())

        if account.net_liquidation > 0:  # fresh marks for the circuit breakers
            await self._store.record_equity(
                at=now, net_liquidation=account.net_liquidation, cash=account.cash
            )
        active = await self._active_stops(orders)
        stops = active.levels
        positions: dict[str, Position] = {}
        for bp in broker_positions:
            known = self._instruments.get(bp.symbol)
            if known is None:
                raise UnknownInstrumentError(bp.symbol)
            positions[bp.symbol] = Position(
                known, bp.quantity, bp.average_cost, stops.get(bp.symbol)
            )

        pending: list[PendingOrder] = []
        for order in orders:
            if order.parent_id is not None or order.limit_price is None:
                continue
            known = self._instruments.get(order.symbol)
            if known is None:
                raise UnknownInstrumentError(order.symbol)
            remaining = order.quantity - order.filled_quantity
            pending.append(PendingOrder(known, order.side, remaining, order.limit_price))

        involved = {instrument.symbol: instrument}
        involved.update({p.instrument.symbol: p.instrument for p in positions.values()})
        involved.update({p.instrument.symbol: p.instrument for p in pending})
        quotes: dict[str, Quote] = {}
        for symbol, inst in involved.items():
            quote = await self._quotes(inst)
            if quote is not None:
                quotes[symbol] = quote

        return RiskContext(
            now=now,
            account=account,
            positions=positions,
            pending=pending,
            protected=active.coverage,
            quotes=quotes,
            session=self._sessions(instrument, now),
            breakers=await self.trading_status(now),
            orders_last_minute=await self._store.count_orders_since(now - timedelta(minutes=1)),
            orders_today=await self._store.count_orders_since(day_start(now)),
        )


def _child_ids(request: OrderRequest) -> list[str]:
    ids = [request.stop_order_id]
    if request.take_profit_price is not None:
        ids.append(request.take_profit_order_id)
    return ids


@dataclass(frozen=True, slots=True)
class _Snapshot:
    account: Account
    positions: tuple[BrokerPosition, ...]
    orders: tuple[BrokerOrder, ...]
    booked: dict[str, int]
    actual: dict[str, int]


@dataclass(frozen=True, slots=True)
class _Stops:
    coverage: dict[str, int]  # shares really protected, per symbol
    levels: dict[str, Decimal]  # the lowest active stop, per symbol


_CENT = Decimal("0.01")


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _identity_mismatch(stored: StoredOrder, view: BrokerOrder) -> str | None:
    """Is the broker's order really the one Jarvis journaled under this id?"""
    if view.symbol != stored.symbol:
        return f"symbol {view.symbol} i stället för {stored.symbol}"
    if view.side.value != stored.side:
        return "fel riktning"
    if (
        view.limit_price is not None
        and stored.limit_price is not None
        and view.limit_price != stored.limit_price
    ):
        return f"limitpris {view.limit_price} i stället för {stored.limit_price}"
    if stored.parent_id is None and view.quantity != stored.quantity:
        return f"antal {view.quantity} i stället för {stored.quantity}"
    return None


def _describe(positions: Mapping[str, int]) -> str:
    if not positions:
        return "inga innehav"
    return ", ".join(f"{qty} {symbol}" for symbol, qty in sorted(positions.items()))
