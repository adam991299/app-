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
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
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
from jarvis.runner.selection import best_first, worth_it
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
        self._day: date | None = None
        self._skipped = 0  # setups today whose costs would eat the expected result
        self._share_price: dict[str, Decimal] = {}  # symbol -> one share today, base currency

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
        now = self._clock()
        approval = await self._store.latest_validation(NAME)
        if approval is None or not approval[0] or approval[2] is None or approval[1] <= 0:
            await self._publish(now, Status.NOT_VALIDATED)
            return
        params, edge_r = params_from(approval[2]), approval[1]
        try:
            session = session_at(self._exchange, now)
        except CalendarRangeError:
            await self._publish(now, Status.MARKET_CLOSED)
            return
        opens, closes = session.opens_at, session.closes_at
        if opens is None or closes is None or not session.is_open(now):
            await self._publish(now, Status.MARKET_CLOSED)
            return
        if now >= flat_time(closes, params):
            for entry_id in await self._open_day_trades():
                if await self._store.order(entry_id) is not None:
                    await self._engine.close_position(
                        entry_id, "Daytrade stängd före börsens slut."
                    )
            await self._publish(now, Status.CLOSING)
            return
        if not await self._may_open_more(now):
            return
        if self._day != now.date():
            self._day, self._skipped, self._share_price = now.date(), 0, {}
        max_position = await self._max_position_base(now)
        found: list[tuple[EntrySignal, _Setup]] = []
        for symbol, instrument in self._instruments.items():
            signal_id, after = await self._next_signal(symbol, now)
            if signal_id is None:
                continue
            newest_end = opens + ((now - opens) // BAR) * BAR
            if self._checked.get(symbol) == newest_end:
                continue  # no new 5-minute bar since the last look (IBKR pacing limits)
            if self._share_price.get(symbol, Decimal(0)) > max_position:
                continue  # not even one share fits in the budget today (D31)
            self._checked[symbol] = newest_end
            bars = await self._market.intraday_bars(instrument, now=now)
            todays = [b for b in bars if b.at >= opens]
            fx = await self._fx_to_base(instrument.currency)
            if todays and fx is not None:
                self._share_price[symbol] = todays[-1].close * fx
            setup = setup_for(todays, closes, params, after)
            if setup is None or setup.signal_at + BAR < newest_end:
                continue  # no breakout, or it happened earlier and the move is no longer fresh
            plan = _Setup(signal_id, instrument, setup, bool(after))
            try:
                signal = await self._signal(plan, params, edge_r)
            except BrokerError:
                logger.exception("could not size the day trade for %s", symbol)
                continue
            if signal is None:
                continue
            if not worth_it(signal, self._risk):
                self._skipped += 1  # the costs would eat the expected result
                continue
            found.append((signal, plan))
        for _, plan in best_first(found):  # the largest expected result after costs first
            try:
                fresh = await self._signal(plan, params, edge_r)  # sized with the cash left now
                if fresh is None or not worth_it(fresh, self._risk):
                    continue
                result = await self._engine.submit_entry(fresh)
                logger.info("day trade %s: %s %s", fresh.signal_id, result.outcome, result.reasons)
            except BrokerError:
                logger.exception("day-trade entry for %s failed", plan.instrument.symbol)
            if not await self._may_open_more(now):
                return
        if self._skipped:
            await self._may_open_more(now)  # publish how many were skipped for costs

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
        """Checks the day-trading limits, publishes the outcome and says whether a new day
        trade may be opened. Anything that cannot be checked counts as a stop (rule 2)."""
        open_count = len(await self._open_day_trades())
        results = await self._store.closed_results(NAME, day_start(now))
        in_base: list[Decimal] = []
        for amount, currency in results:
            fx = await self._fx_to_base(currency)
            if fx is None:
                await self._publish(now, Status.UNKNOWN, open_count=open_count)
                return False
            in_base.append(amount * fx)
        try:
            account = await self._broker.account()
        except BrokerError:
            await self._publish(now, Status.UNKNOWN, open_count=open_count)
            return False
        budget = await self._store.budget_pct(now)
        status = day_status(
            in_base,
            account.net_liquidation * budget / 100,  # the limits apply to Jarvis's share
            self._risk,
            open_count=open_count,
        )
        await self._publish(
            now,
            status,
            open_count=open_count,
            day_result=sum(in_base, Decimal(0)),
            losses_in_row=losses_in_row(in_base),
        )
        return status is Status.ACTIVE

    async def _fx_to_base(self, currency: str) -> Decimal | None:
        """Today's rate from ``currency`` to the base currency, from a live quote of a
        traded instrument in that currency."""
        for instrument in self._instruments.values():
            if instrument.currency == currency:
                quote = await self._market.quote(instrument)
                return None if quote is None else quote.fx_to_base
        return None

    async def _publish(
        self,
        now: datetime,
        status: Status,
        *,
        open_count: int | None = None,
        day_result: Decimal | None = None,
        losses_in_row: int | None = None,
    ) -> None:
        limits = self._risk.daytrading
        await self._store.save_strategy_state(
            NAME,
            {
                "status": status.value,
                "open_count": open_count,
                "max_open": self._risk.concurrency.max_concurrent_daytrades,
                "day_result": None if day_result is None else str(day_result),
                "losses_in_row": losses_in_row,
                "max_daily_loss_pct": limits.max_daily_loss_pct,
                "pause_after_losses": limits.pause_after_consecutive_losses,
                "skipped_for_costs": self._skipped,
            },
            at=now,
        )

    async def _max_position_base(self, now: datetime) -> Decimal:
        """The largest position the budget allows in one stock, in the base currency
        (infinite when the account cannot be read: the risk engine decides then)."""
        try:
            account = await self._broker.account()
        except BrokerError:
            return Decimal("Infinity")
        risk = apply_profile(self._risk, await self._store.risk_profile(now))
        managed = account.net_liquidation * await self._store.budget_pct(now) / 100
        return managed * Decimal(str(risk.portfolio.max_position_pct)) / 100

    async def _signal(
        self, plan: _Setup, params: OrbParameters, edge_r: float
    ) -> EntrySignal | None:
        """The entry for a setup, sized with the account as it is now, or None."""
        instrument, setup = plan.instrument, plan.setup
        quote = await self._market.quote(instrument)
        if quote is None:
            return None
        limit = round_down(quote.last * MARKETABLE)
        stop = setup.range_low
        if limit <= stop:
            return None
        account = await self._broker.account()
        risk = apply_profile(self._risk, await self._store.risk_profile(self._clock()))
        reserve = account.net_liquidation * Decimal(str(risk.portfolio.min_cash_reserve_pct)) / 100
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
            return None
        risk_amount = sized.quantity * (limit - stop) * quote.fx_to_base
        round_trip = 2 * self._costs.total(sized.quantity, float(limit), 1e9)
        return EntrySignal(
            signal_id=plan.signal_id,
            strategy=NAME,
            instrument=instrument,
            quantity=sized.quantity,
            limit_price=limit,
            stop_price=stop,
            take_profit_price=setup.target(limit, params),
            expected_edge=Decimal(str(edge_r)) * risk_amount,
            estimated_cost=Decimal(str(round_trip)) * quote.fx_to_base,
            explanation_sv=(
                f"Daytrade igen: kursen bröt över dagens högsta nivå ({price_sv(setup.level)}). "
                if plan.again
                else f"Daytrade: kursen bröt över de första {params.range_minutes} "
                f"minuternas högsta nivå ({price_sv(setup.level)}). "
            )
            + f"Stopp vid öppningsintervallets lägsta nivå {price_sv(stop)}.",
            features={"level": str(setup.level), "range_low": str(stop)},
        )


@dataclass(frozen=True, slots=True)
class _Setup:
    signal_id: str
    instrument: Instrument
    setup: OrbSetup
    again: bool


class Status(StrEnum):
    NOT_VALIDATED = "not_validated"
    MARKET_CLOSED = "market_closed"
    ACTIVE = "active"
    FULL = "full"
    LOSSES_IN_ROW = "losses_in_row"
    DAILY_LOSS = "daily_loss"
    CLOSING = "closing"
    UNKNOWN = "unknown"


def losses_in_row(results: list[Decimal]) -> int:
    count = 0
    for result in reversed(results):
        if result >= 0:
            break
        count += 1
    return count


def day_status(results: list[Decimal], equity: Decimal, risk: Risk, *, open_count: int) -> Status:
    """Whether a new day trade may be opened, from today's closed results (base currency,
    oldest first) and the capital."""
    limits = risk.daytrading
    if losses_in_row(results) >= limits.pause_after_consecutive_losses:
        return Status.LOSSES_IN_ROW
    if sum(results, Decimal(0)) <= -equity * Decimal(str(limits.max_daily_loss_pct)) / 100:
        return Status.DAILY_LOSS
    if open_count >= risk.concurrency.max_concurrent_daytrades:
        return Status.FULL
    return Status.ACTIVE


def price_sv(value: Decimal) -> str:
    """A price the Swedish way for explanations, e.g. 151,95."""
    return f"{value:.2f}".replace(".", ",")
