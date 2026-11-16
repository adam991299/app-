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
from jarvis.risk.engine import MarketSession
from jarvis.runner.daytrade import DayTrader
from jarvis.store.repo import Store
from jarvis.strategy.orb import BAR, IntradayBar, OrbParameters, params_dict
from tests.factories import instrument

D = Decimal
# Monday 16 Nov 2026: NYSE opens 14:30 and closes 21:00 UTC
OPEN = datetime(2026, 11, 16, 14, 30, tzinfo=UTC)
FRESH = OPEN + timedelta(minutes=20, seconds=30)  # newest finished bar: 14:45-14:50
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
        self.calls = 0

    async def quote(self, inst: Instrument) -> Quote | None:
        price = self.prices.get(inst.symbol)
        return None if price is None else Quote(inst.symbol, price, D(1), self.clock.now)

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
            close = D(102) if i == self.breakout_bar else D(100)
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
    store: Store, now: datetime = FRESH, risk: Risk | None = None
) -> tuple[DayTrader, Broker, Market, Clock]:
    clock = Clock(now)
    sim = Broker(cash=D(100000), clock=clock)
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
    assert results[0] > 0
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
