"""Day trading during the US session (spec §6.2.1) with the opening range breakout.

Runs only when the ORB strategy's latest validation passed. Limits of its own:
- at most ``max_concurrent_daytrades`` positions at a time,
- no new day trades after the day's day-trading loss reaches ``max_daily_loss_pct`` of the
  capital, or after ``pause_after_consecutive_losses`` losses in a row,
- every day trade is sold ``flat_minutes`` before the close.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from jarvis.broker import BrokerAdapter, BrokerError
from jarvis.broker.models import OrderStatus
from jarvis.config.settings import Risk
from jarvis.domain import Instrument
from jarvis.domain.models import Quote
from jarvis.domain.ticks import round_down
from jarvis.execution.engine import EntrySignal, ExecutionEngine
from jarvis.markets.calendar import CalendarRangeError, Exchange, session_at
from jarvis.research.costs import CostModel
from jarvis.risk.profiles import apply_profile
from jarvis.risk.sizing import size_position
from jarvis.store.periods import day_start
from jarvis.store.repo import Store
from jarvis.strategy.orb import (
    BAR,
    MAX_TRADES_PER_SYMBOL,
    NAME,
    IntradayBar,
    OrbParameters,
    OrbSetup,
    flat_time,
    params_from,
    setup_for,
)

logger = logging.getLogger(__name__)
MARKETABLE = Decimal("1.002")


class IntradaySource(Protocol):
    async def quote(self, instrument: Instrument) -> Quote | None: ...

    async def intraday_bars(
        self, instrument: Instrument, *, now: datetime, days: int = 1
    ) -> list[IntradayBar]: ...


class DayTrader:
    def __init__(
        self,
        *,
        broker: BrokerAdapter,
        engine: ExecutionEngine,
        market: IntradaySource,
        store: Store,
        instruments: Mapping[str, Instrument],
        clock: Callable[[], datetime],
        risk: Risk,
        costs: CostModel | None = None,
        exchange: Exchange = Exchange.NYSE,
    ) -> None:
        self._broker = broker
        self._engine = engine
        self._market = market
        self._store = store
        self._instruments = instruments
        self._clock = clock
        self._risk = risk
        self._costs = costs or CostModel()
        self._exchange = exchange
        self._checked: dict[str, datetime] = {}  # symbol -> end of the newest bar looked at

    async def _open_day_trades(self) -> list[str]:
        """Entry ids of ORB brackets that still hold shares or still wait to be bought."""
        open_ids = set()
        for order in await self._store.open_orders():
            if order.strategy != NAME:
                continue
            if order.kind == "entry" and order.status is not OrderStatus.NEW:
                open_ids.add(order.client_order_id)
            elif order.kind == "stop" and order.parent_id is not None:
                open_ids.add(order.parent_id)
        return sorted(open_ids)

    async def tick(self) -> None:
        approval = await self._store.latest_validation(NAME)
        if approval is None or not approval[0] or approval[2] is None or approval[1] <= 0:
            return
        params, edge_r = params_from(approval[2]), approval[1]
        now = self._clock()
        try:
            session = session_at(self._exchange, now)
        except CalendarRangeError:
            return
        opens, closes = session.opens_at, session.closes_at
        if opens is None or closes is None or not session.is_open(now):
            return
        if now >= flat_time(closes, params):
            for entry_id in await self._open_day_trades():
                if await self._store.order(entry_id) is not None:
                    await self._engine.close_position(
                        entry_id, "Daytrade stängd före börsens slut."
                    )
            return
        if not await self._may_open_more(now):
            return
        for symbol, instrument in self._instruments.items():
            signal_id, after = await self._next_signal(symbol, now)
            if signal_id is None:
                continue
            newest_end = opens + ((now - opens) // BAR) * BAR
            if self._checked.get(symbol) == newest_end:
                continue  # no new 5-minute bar since the last look (IBKR pacing limits)
            self._checked[symbol] = newest_end
            bars = await self._market.intraday_bars(instrument, now=now)
            todays = [b for b in bars if b.at >= opens]
            setup = setup_for(todays, closes, params, after)
            if setup is None or setup.signal_at + BAR < newest_end:
                continue  # no breakout, or it happened earlier and the move is no longer fresh
            try:
                await self._enter(signal_id, instrument, setup, params, edge_r, again=bool(after))
            except BrokerError:
                logger.exception("day-trade entry for %s failed", symbol)
            if not await self._may_open_more(now):
                return

    async def _next_signal(self, symbol: str, now: datetime) -> tuple[str | None, datetime | None]:
        """The id for the symbol's next day trade today and when its previous one ended, or
        (None, None) while one is still open or the day's maximum is used."""
        day = now.date().isoformat()
        previous = None
        for number in range(1, MAX_TRADES_PER_SYMBOL + 1):
            signal_id = f"{NAME}:{symbol}:{day}" + ("" if number == 1 else f":{number}")
            if await self._store.order(signal_id) is None:
                break
            previous = signal_id
        else:
            return None, None
        if previous is None:
            return signal_id, None
        for order in await self._store.open_orders():
            related = order.client_order_id.startswith(previous + ".")
            if order.client_order_id == previous or order.parent_id == previous or related:
                return None, None
        return signal_id, await self._store.last_fill_at(previous) or now

    async def _may_open_more(self, now: datetime) -> bool:
        limits = self._risk.daytrading
        if len(await self._open_day_trades()) >= self._risk.concurrency.max_concurrent_daytrades:
            return False
        results = await self._store.closed_results(NAME, day_start(now))
        losses_in_row = 0
        for result in reversed(results):
            if result >= 0:
                break
            losses_in_row += 1
        if losses_in_row >= limits.pause_after_consecutive_losses:
            return False
        try:
            account = await self._broker.account()
        except BrokerError:
            return False
        limit = account.net_liquidation * Decimal(str(limits.max_daily_loss_pct)) / 100
        return sum(results, Decimal(0)) > -limit

    async def _enter(
        self,
        signal_id: str,
        instrument: Instrument,
        setup: OrbSetup,
        params: OrbParameters,
        edge_r: float,
        *,
        again: bool,
    ) -> None:
        quote = await self._market.quote(instrument)
        if quote is None:
            return
        limit = round_down(quote.last * MARKETABLE)
        stop = setup.range_low
        if limit <= stop:
            return
        account = await self._broker.account()
        risk = apply_profile(self._risk, await self._store.risk_profile(self._clock()))
        reserve = account.net_liquidation * Decimal(str(risk.portfolio.min_cash_reserve_pct)) / 100
        sized = size_position(
            instrument=instrument,
            equity=account.net_liquidation,
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
        result = await self._engine.submit_entry(
            EntrySignal(
                signal_id=signal_id,
                strategy=NAME,
                instrument=instrument,
                quantity=sized.quantity,
                limit_price=limit,
                stop_price=stop,
                take_profit_price=setup.target(limit, params),
                expected_edge=Decimal(str(edge_r)) * risk_amount,
                estimated_cost=Decimal(str(round_trip)) * quote.fx_to_base,
                explanation_sv=(
                    f"Daytrade igen: kursen bröt över dagens högsta nivå ({setup.level}). "
                    if again
                    else f"Daytrade: kursen bröt över de första {params.range_minutes} "
                    f"minuternas högsta nivå ({setup.level}). "
                )
                + f"Stopp vid öppningsintervallets lägsta nivå {stop}.",
                features={"level": str(setup.level), "range_low": str(stop)},
            )
        )
        logger.info("day trade %s: %s %s", signal_id, result.outcome, result.reasons)
