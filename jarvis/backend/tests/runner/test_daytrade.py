from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from jarvis.broker import BrokerError
from jarvis.broker.sim import SimBroker
from jarvis.config.settings import Concurrency, Daytrading, Risk
from jarvis.domain import Instrument, Quote
from jarvis.domain.models import Account
from jarvis.execution.engine import ExecutionEngine
from jarvis.research.costs import CostModel
from jarvis.risk.engine import MarketSession
from jarvis.runner.daytrade import DayTrader
from jarvis.store.repo import Store
from jarvis.strategy.orb import BAR, IntradayBar, OrbParameters, params_dict
from tests.factories import instrument

D = Decimal
# Monday 16 Nov 2026: NYSE opens 14:30 and closes 21:00 UTC
OPEN = datetime(2026, 11, 16, 14, 30, tzinfo=UTC)
FRESH = OPEN + timedelta(minutes=20, seconds=30)  # newest finished bar: 14:45-14:50
START_CASH = Decimal(100000)
SYMBOLS = {"AAPL": "technology", "XOM": "energy", "JNJ": "health"}


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class Market:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.prices: dict[str, Decimal] = dict.fromkeys(SYMBOLS, D(102))
        self.breakout_bar = 3  # index of the bar that closes above the range
        self.closes: dict[int, Decimal] = {}  # later closes by bar index, for every symbol
        self.calls = 0
        self.fx = D(1)  # USD to the account's base currency

    async def quote(self, inst: Instrument) -> Quote | None:
        price = self.prices.get(inst.symbol)
        return None if price is None else Quote(inst.symbol, price, self.fx, self.clock.now)

    async def intraday_bars(
        self, inst: Instrument, *, now: datetime, days: int = 1
    ) -> list[IntradayBar]:
        self.calls += 1
        yesterday = IntradayBar(OPEN - timedelta(days=1), D(50), D(200), D(50), D(150), 1)
        bars = [yesterday]
        for i in range(12):
            at = OPEN + i * BAR
            if at + BAR > now:
                break
            close = self.closes.get(i, D(102) if i == self.breakout_bar else D(100))
            bars.append(IntradayBar(at, D(100), max(close, D(101)), D(99), close, 1000))
        return bars


class Alerts:
    async def send(self, level: object, message_sv: str) -> None:
        return None


class Broker(SimBroker):
    fail_account = False

    async def account(self) -> Account:
        if self.fail_account:
            raise BrokerError("gateway busy")
        return await super().account()


async def approve(store: Store, *, passed: bool = True, edge: float = 0.3) -> None:
    await store.save_validation(
        "orb",
        params=params_dict(OrbParameters()),
        passed=passed,
        edge_r=edge,
        report_sv="Godkänd." if passed else "Underkänd.",
        at=OPEN,
    )


async def make(
    store: Store,
    now: datetime = FRESH,
    risk: Risk | None = None,
    costs: CostModel | None = None,
    cash: Decimal = START_CASH,
) -> tuple[DayTrader, Broker, Market, Clock]:
    clock = Clock(now)
    sim = Broker(cash=cash, clock=clock)
    for symbol in SYMBOLS:
        sim.set_price(symbol, D(102))
    market = Market(clock)
    instruments = {s: instrument(s, sector=sector) for s, sector in SYMBOLS.items()}
    rules = risk or Risk()
    engine = ExecutionEngine(
        broker=sim,
        store=store,
        risk=rules,
        instruments=instruments,
        quotes=market.quote,
        sessions=lambda i, n: MarketSession(n - timedelta(hours=2), n + timedelta(hours=4)),
        clock=clock,
        clock_drift=lambda: 0.0,
        alerts=Alerts(),
    )
    await sim.connect()
    await engine.recover()
    trader = DayTrader(
        broker=sim,
        engine=engine,
        market=market,
        store=store,
        instruments=instruments,
        clock=clock,
        risk=rules,
        costs=costs,
    )
    return trader, sim, market, clock


async def entries(store: Store) -> list[str]:
    """Day-trade entries sent today, whatever their state."""
    ids = [f"orb:{symbol}:2026-11-16" for symbol in sorted(SYMBOLS)]
    return [i for i in ids if await store.order(i) is not None]


async def test_nothing_happens_without_a_passed_validation(store: Store) -> None:
    trader, _, market, _ = await make(store)
    await trader.tick()
    await approve(store, passed=False)
    await trader.tick()
    assert market.calls == 0
    assert await store.open_orders() == []


async def test_fresh_breakout_opens_a_bracket_with_the_range_low_as_stop(store: Store) -> None:
    trader, sim, _, _ = await make(store)
    await approve(store)
    await trader.tick()
    entry = await store.order("orb:AAPL:2026-11-16")
    stop = await store.order("orb:AAPL:2026-11-16.stop")
    target = await store.order("orb:AAPL:2026-11-16.tp")
    assert entry is not None
    assert stop is not None
    assert target is not None
    assert entry.limit_price == D("102.20")
    assert stop.stop_price == D(99)
    assert target.limit_price == D("102.20") + 2 * (D("102.20") - D(99))
    assert entry.quantity > 0
    assert {p.symbol for p in await sim.positions()} == set(SYMBOLS)


async def test_each_bar_is_looked_at_once_and_old_breakouts_are_ignored(store: Store) -> None:
    trader, _, market, clock = await make(store, now=FRESH + timedelta(minutes=10))
    await approve(store)
    await trader.tick()
    await trader.tick()  # same newest bar: no new requests
    assert market.calls == len(SYMBOLS)
    assert await store.open_orders() == []  # the breakout bar ended ten minutes ago
    clock.now += BAR
    await trader.tick()
    assert market.calls == 2 * len(SYMBOLS)


async def test_no_breakout_or_unusable_prices_open_nothing(store: Store) -> None:
    trader, _, market, clock = await make(store)
    await approve(store)
    market.breakout_bar = 99
    await trader.tick()
    assert await store.open_orders() == []
    market.breakout_bar = 3
    market.prices = {"AAPL": D(98), "XOM": D("0.01")}  # under the stop / too cheap to size
    clock.now += BAR
    market.breakout_bar = 4
    await trader.tick()
    assert await store.open_orders() == []


async def test_entries_stop_at_the_concurrency_limit(store: Store) -> None:
    risk = Risk(concurrency=Concurrency(max_concurrent_daytrades=2))
    trader, _, _, _ = await make(store, risk=risk)
    await approve(store)
    await trader.tick()
    assert await entries(store) == ["orb:AAPL:2026-11-16", "orb:XOM:2026-11-16"]
    trader2, *_ = await make(store, risk=risk)
    await trader2.tick()  # a restart sees the open day trades in the store
    assert len(await entries(store)) == 2


async def test_all_day_trades_are_sold_before_the_close(store: Store) -> None:
    trader, sim, _, clock = await make(store)
    await approve(store)
    await trader.tick()
    clock.now = datetime(2026, 11, 16, 20, 46, tzinfo=UTC)
    await trader.tick()
    assert await sim.positions() == ()
    assert [o for o in await store.open_orders() if o.strategy == "orb"] == []


async def test_a_loss_in_a_row_pauses_day_trading(store: Store) -> None:
    risk = Risk(daytrading=Daytrading(pause_after_consecutive_losses=1, max_daily_loss_pct=2.0))
    trader, sim, market, clock = await make(
        store, risk=risk.model_copy(update={"concurrency": Concurrency(max_concurrent_daytrades=1)})
    )
    await approve(store)
    await trader.tick()
    sim.set_price("AAPL", D(98))  # stop at 99 fills
    await trader._engine.reconcile()
    clock.now += BAR
    market.breakout_bar = 4
    await trader.tick()
    assert await store.closed_results("orb", OPEN) != []
    assert await store.order("orb:XOM:2026-11-16") is None


async def test_the_daily_loss_limit_pauses_day_trading(store: Store) -> None:
    risk = Risk(
        concurrency=Concurrency(max_concurrent_daytrades=1),
        daytrading=Daytrading(max_daily_loss_pct=0.1),
    )
    trader, sim, market, clock = await make(store, risk=risk)
    await approve(store)
    await trader.tick()
    sim.set_price("AAPL", D(98))
    await trader._engine.reconcile()
    clock.now += BAR
    market.breakout_bar = 4
    await trader.tick()
    assert await store.order("orb:XOM:2026-11-16") is None


async def test_a_win_resets_the_loss_streak(store: Store) -> None:
    risk = Risk(
        concurrency=Concurrency(max_concurrent_daytrades=1),
        daytrading=Daytrading(pause_after_consecutive_losses=1),
    )
    trader, sim, market, clock = await make(store, risk=risk)
    await approve(store)
    await trader.tick()
    sim.set_price("AAPL", D(120))  # target fills
    await trader._engine.reconcile()
    clock.now += BAR
    market.breakout_bar = 4
    await trader.tick()
    results = await store.closed_results("orb", OPEN)
    assert len(results) == 1
    assert results[0][0] > 0
    assert results[0][1] == "USD"
    assert await store.order("orb:XOM:2026-11-16") is not None


async def test_an_unreachable_account_blocks_new_entries(store: Store) -> None:
    trader, sim, _, _ = await make(store)
    await approve(store)
    sim.fail_account = True
    await trader.tick()
    assert await store.open_orders() == []


async def test_a_failed_entry_does_not_stop_the_other_symbols(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    trader, _, _, _ = await make(store)
    await approve(store)
    original = trader._engine.submit_entry
    calls: list[str] = []

    async def flaky(signal: object) -> object:
        calls.append(signal.signal_id)  # type: ignore[attr-defined]
        if len(calls) == 1:
            raise BrokerError("rejected")
        return await original(signal)  # type: ignore[arg-type]

    monkeypatch.setattr(trader._engine, "submit_entry", flaky)
    await trader.tick()
    assert len(calls) == len(SYMBOLS)
    assert len(await entries(store)) == len(SYMBOLS) - 1


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 11, 15, 16, tzinfo=UTC),  # Sunday
        datetime(2026, 11, 16, 13, tzinfo=UTC),  # before the open
        datetime(2040, 1, 2, 16, tzinfo=UTC),  # outside the calendar
    ],
)
async def test_nothing_runs_outside_the_session(store: Store, now: datetime) -> None:
    trader, _, market, _ = await make(store, now=now)
    await approve(store)
    await trader.tick()
    assert market.calls == 0


async def test_the_same_stock_is_traded_again_after_a_new_high(store: Store) -> None:
    trader, sim, market, clock = await make(store)
    await approve(store)
    await trader.tick()
    first = "orb:AAPL:2026-11-16"
    for number, bar_index, price in ((2, 5, D(103)), (3, 7, D(104))):
        clock.now = OPEN + bar_index * BAR - BAR / 2  # the exit is before the signal bar
        await trader.tick()
        assert await store.order(f"{first}:{number}") is None  # the last trade is still open
        sim.set_price("AAPL", D(130))  # the target fills
        await trader._engine.reconcile()
        market.closes[bar_index] = price  # a close above the day's high so far
        market.prices["AAPL"] = price
        sim.set_price("AAPL", price)
        clock.now = OPEN + (bar_index + 1) * BAR + timedelta(seconds=30)
        await trader.tick()
        again = await store.order(f"{first}:{number}")
        assert again is not None
    assert await store.order("orb:XOM:2026-11-16:2") is None  # XOM still holds its first trade
    sim.set_price("AAPL", D(130))
    await trader._engine.reconcile()
    market.closes[9] = D(105)
    market.prices["AAPL"] = D(105)
    clock.now = OPEN + 10 * BAR + timedelta(seconds=30)
    await trader.tick()
    assert await store.order(f"{first}:4") is None  # three a day is the maximum


async def stopped_out(store: Store, fx: Decimal) -> tuple[DayTrader, Market, Clock]:
    """One AAPL day trade stopped out at 98 (a loss of a few hundred dollars), then the next
    bar breaks out in XOM."""
    risk = Risk(concurrency=Concurrency(max_concurrent_daytrades=1))
    trader, sim, market, clock = await make(store, risk=risk)
    await approve(store)
    await trader.tick()
    sim.set_price("AAPL", D(98))
    await trader._engine.reconcile()
    market.fx = fx
    clock.now += BAR
    market.breakout_bar = 4
    await trader.tick()
    return trader, market, clock


async def test_the_daily_loss_is_counted_in_the_base_currency(store: Store) -> None:
    await stopped_out(store, D(1))
    assert await store.order("orb:XOM:2026-11-16") is not None  # a $-loss below 1 % of 100 000
    state = await store.strategy_state("orb")
    assert state is not None
    assert state[1]["status"] in ("active", "full")


async def test_the_same_loss_in_kronor_pauses_day_trading(store: Store) -> None:
    await stopped_out(store, D(10))  # the loss is ten times larger in the base currency
    assert await store.order("orb:XOM:2026-11-16") is None
    state = await store.strategy_state("orb")
    assert state is not None
    assert state[1]["status"] == "daily_loss"
    assert D(state[1]["day_result"]) < -1000
    assert state[1]["losses_in_row"] == 1


async def test_without_an_exchange_rate_day_trading_waits(store: Store) -> None:
    trader, market, clock = await stopped_out(store, D(1))
    market.prices = {}
    clock.now += BAR
    await trader.tick()
    state = await store.strategy_state("orb")
    assert state is not None
    assert state[1]["status"] == "unknown"


async def test_the_state_says_why_nothing_trades(store: Store) -> None:
    trader, *_ = await make(store)
    await trader.tick()
    state = await store.strategy_state("orb")
    assert state is not None
    assert state[1]["status"] == "not_validated"


async def test_the_trade_with_the_largest_expected_result_goes_first(store: Store) -> None:
    """XOM's wider stop allows a larger risk within the limits: more expected profit."""
    trader, sim, market, _ = await make(
        store, risk=Risk(concurrency=Concurrency(max_concurrent_daytrades=1))
    )
    await approve(store)
    market.prices["XOM"] = D(200)
    sim.set_price("XOM", D(200))
    await trader.tick()
    assert await entries(store) == ["orb:XOM:2026-11-16"]


async def test_trades_whose_costs_eat_the_result_are_skipped(store: Store) -> None:
    trader, *_ = await make(store, costs=CostModel(commission_min=500.0))
    await approve(store)
    await trader.tick()
    assert await entries(store) == []
    state = await store.strategy_state("orb")
    assert state is not None
    assert state[1]["skipped_for_costs"] == len(SYMBOLS)


async def test_stocks_the_budget_cannot_buy_are_not_followed(store: Store) -> None:
    trader, _, market, clock = await make(store, now=FRESH + BAR, cash=D(500))
    await approve(store)
    await trader.tick()  # one share costs about 100: more than 10 % of 500
    calls = market.calls
    clock.now += BAR
    await trader.tick()
    assert market.calls == calls  # no more requests for stocks that cannot be bought today
    clock.now += timedelta(days=1)
    await trader.tick()  # a new day: prices are looked at again (the session is closed here)


async def test_a_broker_error_while_sizing_skips_only_that_stock(store: Store) -> None:
    trader, sim, _, _ = await make(store)
    await approve(store)
    original = sim.account
    calls = {"n": 0}

    async def flaky() -> Account:
        calls["n"] += 1
        if calls["n"] == 3:  # the first sizing call (after the limit checks)
            raise BrokerError("busy")
        return await original()

    sim.account = flaky  # type: ignore[method-assign]
    await trader.tick()
    assert len(await entries(store)) == len(SYMBOLS) - 1
