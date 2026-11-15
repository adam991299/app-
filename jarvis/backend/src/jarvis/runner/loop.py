"""Runs Jarvis around the clock: connect, recover, reconcile every minute, and after the
US close update trailing stops and look for new setups.

New entries are not sent yet: the risk engine needs a validated expected edge per trade,
which comes from the backtest (decision D18). Setups are logged openly instead.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from datetime import date, datetime, timedelta
from typing import Protocol

from jarvis.broker import BrokerAdapter, BrokerError, BrokerUnavailableError
from jarvis.broker.models import OrderStatus
from jarvis.domain import Instrument, Quote
from jarvis.execution.engine import ExecutionEngine, Outcome
from jarvis.markets.calendar import CalendarRangeError, Exchange, session_at
from jarvis.store.repo import Store
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import TrendParameters, entry_setup, trailing_stop

logger = logging.getLogger(__name__)
HISTORY_YEARS = 1


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
        day = self._close_due(self._clock())
        if day is not None:
            await self.after_close(day)

    async def after_close(self, day: date) -> None:
        await self.load_instruments()  # retry symbols that could not be loaded before
        bars: dict[str, list[Bar]] = {}
        for symbol, instrument in self._instruments.items():
            bars[symbol] = await self._market.daily_bars(
                instrument, years=HISTORY_YEARS, closed_through=day
            )
        await self._update_stops(bars)
        await self._log_setups(bars, day)
        self.last_close_processed = day

    async def _update_stops(self, bars: dict[str, list[Bar]]) -> None:
        for order in await self._store.open_orders():
            if order.kind != "stop" or order.parent_id is None:
                continue
            if order.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
                continue
            history = bars.get(order.symbol, [])
            level = trailing_stop(history, self._params) if history else None
            if level is None:
                continue
            try:
                result = await self._engine.raise_stop(order.parent_id, level)
            except BrokerError:
                logger.exception("could not move stop %s", order.client_order_id)
                continue
            if result.outcome is Outcome.STOP_RAISED:
                logger.info("raised %s to %s", order.client_order_id, level)

    async def _log_setups(self, bars: dict[str, list[Bar]], day: date) -> None:
        for symbol, history in bars.items():
            setup = entry_setup(history, self._params) if history else None
            if setup is None:
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
                    "reason": "no validated expected edge yet (decision D18)",
                },
            )

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
