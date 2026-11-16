"""Runs Jarvis around the clock: connect, recover, reconcile every minute, and after the
US close update trailing stops and look for new setups.

New entries are only sent when the strategy's latest validation passed (decision D18): the
expected edge per trade comes from that validation, measured in R. A setup found after the
close is entered once, at the next session after its opening minutes; otherwise it lapses.
Without a passed validation, setups are only logged.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from jarvis.broker import BrokerAdapter, BrokerError, BrokerUnavailableError
from jarvis.broker.models import OrderStatus
from jarvis.config.settings import Risk
from jarvis.domain import Instrument, Quote
from jarvis.domain.ticks import round_down
from jarvis.execution.engine import EntrySignal, ExecutionEngine, Outcome
from jarvis.markets.calendar import CalendarRangeError, Exchange, session_at
from jarvis.research.costs import CostModel
from jarvis.risk.profiles import apply_profile
from jarvis.risk.sizing import size_position
from jarvis.runner.daytrade import DayTrader, price_sv
from jarvis.store.repo import Store
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import (
    NAME,
    EntrySetup,
    TrendParameters,
    entry_setup,
    params_from,
    signal_id,
    trailing_stop,
)

logger = logging.getLogger(__name__)
HISTORY_YEARS = 1
MARKETABLE = Decimal("1.002")  # entry limit: last price + 0.2 %, then rounded down


@dataclass(frozen=True, slots=True)
class Pending:
    instrument: Instrument
    setup: EntrySetup
    params: TrendParameters
    edge_r: float


class MarketSource(Protocol):
    async def quote(self, instrument: Instrument) -> Quote | None: ...

    async def daily_bars(
        self, instrument: Instrument, *, years: int, closed_through: date
    ) -> list[Bar]: ...

    async def instrument(self, symbol: str, currency: str = "USD") -> Instrument | None: ...


class Runner:
    def __init__(
        self,
        *,
        broker: BrokerAdapter,
        engine: ExecutionEngine,
        market: MarketSource,
        store: Store,
        instruments: MutableMapping[str, Instrument],
        symbols: list[str],
        clock: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        params: TrendParameters | None = None,
        exchange: Exchange = Exchange.NYSE,
        reconcile_seconds: float = 60.0,
        after_close_delay: timedelta = timedelta(minutes=15),
        before_tick: Callable[[], Awaitable[None]] | None = None,
        risk: Risk | None = None,
        costs: CostModel | None = None,
        day_trader: DayTrader | None = None,
        index_fund: Instrument | None = None,
    ) -> None:
        self._broker = broker
        self._engine = engine
        self._market = market
        self._store = store
        self._instruments = instruments
        self._symbols = symbols
        self._clock = clock
        self._sleep = sleep
        self._params = params or TrendParameters()
        self._exchange = exchange
        self._every = reconcile_seconds
        self._delay = after_close_delay
        self._before_tick = before_tick
        self._risk = risk or Risk()
        self._costs = costs or CostModel()
        self._day_trader = day_trader
        self._index_fund = index_fund
        self.pending: list[Pending] = []
        self.last_close_processed: date | None = None

    async def connect(self) -> bool:
        try:
            await self._broker.connect()
        except BrokerUnavailableError:
            logger.warning("IB Gateway not reachable; trading stays halted")
            return False
        return True

    async def start(self, max_wait: float = 60.0) -> None:
        """Connect with growing pauses (1, 2, 4 … up to ``max_wait`` seconds), load the
        universe, then recover the books from the broker."""
        pause = 1.0
        while not await self.connect():
            await self._sleep(pause)
            pause = min(pause * 2, max_wait)
        await self.load_instruments()
        await self._engine.recover()

    async def load_instruments(self) -> None:
        for symbol in self._symbols:
            if symbol in self._instruments:
                continue
            found = await self._market.instrument(symbol)
            if found is None:
                logger.warning("no usable instrument data for %s; it will not be traded", symbol)
                continue
            self._instruments[symbol] = found

    def _close_due(self, now: datetime) -> date | None:
        """The session date to process, if the US close (+ delay) has passed and it has not
        been processed yet."""
        try:
            session = session_at(self._exchange, now)
        except CalendarRangeError:
            logger.error("exchange calendar does not cover %s", now.date())
            return None
        if session.closes_at is None or now < session.closes_at + self._delay:
            return None
        day = session.closes_at.date()
        return None if day == self.last_close_processed else day

    async def tick(self) -> None:
        if self._before_tick is not None:
            await self._before_tick()  # e.g. the clock check, before risk relies on it
        if not self._broker.is_connected():
            await self.connect()
        await self._engine.reconcile()
        now = self._clock()
        if self.pending and self._entry_window_open(now):
            await self.enter_pending()
        if self._day_trader is not None:
            await self._day_trader.tick()
        day = self._close_due(now)
        if day is not None:
            await self.after_close(day)

    def _entry_window_open(self, now: datetime) -> bool:
        try:
            session = session_at(self._exchange, now)
        except CalendarRangeError:
            return False
        if session.opens_at is None or not session.is_open(now):
            return False
        return now >= session.opens_at + timedelta(
            minutes=self._risk.order_safety.avoid_open_minutes
        )

    async def after_close(self, day: date) -> None:
        self.pending = []  # yesterday's setups lapse: a setup gets exactly one session
        await self.load_instruments()  # retry symbols that could not be loaded before
        bars: dict[str, list[Bar]] = {}
        for symbol, instrument in self._instruments.items():
            bars[symbol] = await self._market.daily_bars(
                instrument, years=HISTORY_YEARS, closed_through=day
            )
        approval = await self._store.latest_validation(NAME)
        params, edge_r = self._params, 0.0
        if approval is not None and approval[0] and approval[2] is not None:
            params, edge_r = params_from(approval[2]), approval[1]
        await self._update_stops(bars, params)
        await self._queue_setups(bars, day, params, edge_r)
        await self._record_index_fund(day)
        self.last_close_processed = day

    async def _record_index_fund(self, day: date) -> None:
        """The index fund's close in the base currency, for the honest comparison (§1.5)."""
        if self._index_fund is None:
            return
        quote = await self._market.quote(self._index_fund)
        if quote is None:
            logger.warning("no quote for the index fund %s on %s", self._index_fund.symbol, day)
            return
        await self._store.save_index_fund_close(
            self._index_fund.symbol, day, quote.last, quote.fx_to_base
        )

    async def _update_stops(self, bars: dict[str, list[Bar]], params: TrendParameters) -> None:
        for order in await self._store.open_orders():
            if order.kind != "stop" or order.parent_id is None or order.strategy != NAME:
                continue  # day trades keep their opening-range stop
            if order.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
                continue
            history = bars.get(order.symbol, [])
            level = trailing_stop(history, params) if history else None
            if level is None:
                continue
            try:
                result = await self._engine.raise_stop(order.parent_id, level)
            except BrokerError:
                logger.exception("could not move stop %s", order.client_order_id)
                continue
            if result.outcome is Outcome.STOP_RAISED:
                logger.info("raised %s to %s", order.client_order_id, level)

    async def _queue_setups(
        self, bars: dict[str, list[Bar]], day: date, params: TrendParameters, edge_r: float
    ) -> None:
        for symbol, history in bars.items():
            setup = entry_setup(history, params) if history else None
            if setup is None:
                continue
            if edge_r > 0:
                self.pending.append(Pending(self._instruments[symbol], setup, params, edge_r))
                continue
            await self._store.audit(
                actor="jarvis",
                action="setup_not_traded",
                at=self._clock(),
                details={
                    "symbol": symbol,
                    "day": day.isoformat(),
                    "reference_price": str(setup.reference_price),
                    "stop_price": str(setup.stop_price),
                    "reason": "no passed validation with a positive edge (decision D18)",
                },
            )

    async def enter_pending(self) -> None:
        """Send each queued setup once; whatever happens, it is not retried."""
        queued, self.pending = self.pending, []
        for item in queued:
            try:
                await self._enter(item)
            except BrokerError:
                logger.exception("entry for %s failed", item.instrument.symbol)

    async def _enter(self, item: Pending) -> None:
        instrument, setup = item.instrument, item.setup
        quote = await self._market.quote(instrument)
        if quote is None:
            return
        limit = round_down(quote.last * MARKETABLE)
        stop = setup.stop_price
        if limit <= stop:
            return  # the price already fell through the planned stop
        account = await self._broker.account()
        reserve = (
            account.net_liquidation * Decimal(str(self._risk.portfolio.min_cash_reserve_pct)) / 100
        )
        risk = apply_profile(self._risk, await self._store.risk_profile(self._clock()))
        sized = size_position(
            instrument=instrument,
            equity=account.net_liquidation * await self._store.budget_pct(self._clock()) / 100,
            free_cash=min(account.cash - reserve, account.spendable),
            entry=limit,
            stop=stop,
            fx_to_base=quote.fx_to_base,
            risk=risk,
        )
        if sized.quantity == 0:
            return
        risk_amount = sized.quantity * (limit - stop) * quote.fx_to_base
        round_trip = 2 * self._costs.total(sized.quantity, float(limit), 1e9)
        edge_text = f"{item.edge_r:.2f}".replace(".", ",")  # Swedish decimal comma
        result = await self._engine.submit_entry(
            EntrySignal(
                signal_id=signal_id(instrument.symbol, setup),
                strategy=NAME,
                instrument=instrument,
                quantity=sized.quantity,
                limit_price=limit,
                stop_price=stop,
                expected_edge=Decimal(str(item.edge_r)) * risk_amount,
                estimated_cost=Decimal(str(round_trip)) * quote.fx_to_base,
                explanation_sv=(
                    f"Kursen stängde över sin högsta nivå på {item.params.entry_lookback} dagar "
                    f"({price_sv(setup.channel_high)}). Stopp {price_sv(stop)}. "
                    "Valideringen visar i snitt "
                    f"{edge_text} gånger risken per affär."
                ),
                features={"channel_high": str(setup.channel_high), "atr": str(setup.atr)},
            )
        )
        logger.info("entry %s: %s %s", result.client_order_id, result.outcome, result.reasons)

    async def run(self, stop: asyncio.Event) -> None:
        """Never ends on an error: a failed start is retried, a failed tick is logged and the
        next one runs a minute later. Until the start succeeds nothing trades."""
        while not stop.is_set():
            try:
                await self.start()
                break
            except Exception:
                logger.exception("runner start failed; retrying in a minute")
                await self._sleep(self._every)
        while not stop.is_set():
            try:
                await self.tick()
            except Exception:
                logger.exception("runner tick failed; trying again next minute")
            await self._sleep(self._every)
