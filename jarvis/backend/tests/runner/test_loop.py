from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from jarvis.broker import BrokerError
from jarvis.broker.sim import SimBroker
from jarvis.config.settings import Risk
from jarvis.domain import Instrument, Quote
from jarvis.execution.engine import EntrySignal, ExecutionEngine, Outcome
from jarvis.markets.calendar import Exchange
from jarvis.risk.engine import MarketSession
from jarvis.runner.loop import Runner
from jarvis.store.repo import Store
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import TrendParameters
from tests.factories import instrument

D = Decimal
AAPL = instrument()
PARAMS = TrendParameters(entry_lookback=5, exit_lookback=3, atr_period=3)
# Monday 16 Nov 2026: NYSE closes 21:00 UTC
DURING = datetime(2026, 11, 16, 16, tzinfo=UTC)
AFTER = datetime(2026, 11, 16, 21, 20, tzinfo=UTC)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class Market:
    def __init__(self) -> None:
        self.prices: dict[str, Decimal] = {"AAPL": D(100)}
        self.history: list[Bar] = []
        self.known = {"AAPL": AAPL}
        self.clock: Clock | None = None

    async def quote(self, inst: Instrument) -> Quote | None:
        assert self.clock is not None
        price = self.prices.get(inst.symbol)
        return None if price is None else Quote(inst.symbol, price, D(1), self.clock.now)

    async def daily_bars(self, inst: Instrument, *, years: int, closed_through: date) -> list[Bar]:
        return [b for b in self.history if b.day <= closed_through]

    async def instrument(self, symbol: str, currency: str = "USD") -> Instrument | None:
        return self.known.get(symbol)


class Alerts:
    async def send(self, level: object, message_sv: str) -> None:
        return None


class FlakyConnect(SimBroker):
    def __init__(self, failures: int, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.failures = failures

    async def connect(self) -> None:
        if self.failures:
            self.failures -= 1
            self.go_offline()
            try:
                await super().connect()
            finally:
                self.go_online()
        await super().connect()


def bars_rising(end: date, n: int = 8) -> list[Bar]:
    """Steady rise, then a breakout on the last day. Lows of the last three: 94, 95, 104."""
    out = []
    for i in range(n):
        close = D(90 + i) if i < n - 1 else D(105)
        out.append(Bar(end - timedelta(days=n - 1 - i), close, close + 1, close - 1, close, 1000))
    return out


async def make(
    store: Store, now: datetime, failures: int = 0
) -> tuple[Runner, SimBroker, Market, Clock, list[float]]:
    clock = Clock(now)
    sim = FlakyConnect(failures, cash=D(100000), clock=clock)
    sim.set_price("AAPL", D(100))
    market = Market()
    market.clock = clock
    instruments: dict[str, Instrument] = {}
    engine = ExecutionEngine(
        broker=sim,
        store=store,
        risk=Risk(),
        instruments=instruments,
        quotes=market.quote,
        sessions=lambda i, n: MarketSession(n - timedelta(hours=2), n + timedelta(hours=4)),
        clock=clock,
        clock_drift=lambda: 0.0,
        alerts=Alerts(),
    )
    pauses: list[float] = []

    async def sleep(seconds: float) -> None:
        pauses.append(seconds)

    runner = Runner(
        broker=sim,
        engine=engine,
        market=market,
        store=store,
        instruments=instruments,
        symbols=["AAPL", "GONE"],
        clock=clock,
        sleep=sleep,
        params=PARAMS,
        exchange=Exchange.NYSE,
    )
    return runner, sim, market, clock, pauses


async def test_start_retries_with_growing_pauses_then_recovers(store: Store) -> None:
    runner, sim, _, _, pauses = await make(store, DURING, failures=3)
    await runner.start(max_wait=3)
    assert pauses == [1.0, 2.0, 3.0]
    assert sim.is_connected()
    assert (await store.account_state()) is not None  # recover reconciled and published


async def test_unknown_symbols_are_skipped(store: Store) -> None:
    runner, *_ = await make(store, DURING)
    await runner.start()
    await runner.load_instruments()  # second call: nothing new
    assert list(runner._instruments) == ["AAPL"]


async def test_after_close_raises_stops_and_logs_setups_without_trading(store: Store) -> None:
    runner, sim, market, clock, _ = await make(store, DURING)
    await runner.start()
    entry = await runner._engine.submit_entry(
        EntrySignal(
            signal_id="trend:AAPL:x",
            strategy="trend",
            instrument=AAPL,
            quantity=10,
            limit_price=D(100),
            stop_price=D(90),
            expected_edge=D(100),
            estimated_cost=D(5),
            explanation_sv="Test.",
        )
    )
    assert entry.outcome is Outcome.SUBMITTED
    market.history = bars_rising(date(2026, 11, 16))  # lows 89..96; last 3 lows: 94, 95, 96
    sim.set_price("AAPL", D(105))
    market.prices["AAPL"] = D(105)
    await runner.tick()  # during the session: no after-close work
    assert runner.last_close_processed is None
    clock.now = AFTER
    await runner.tick()
    assert runner.last_close_processed == date(2026, 11, 16)
    stop = await store.known_order("trend:AAPL:x.stop")
    assert stop.stop_price == D(94)
    audit = await store.audit_entries()
    assert ("jarvis", "setup_not_traded") in [(a, b) for a, b, _ in audit]
    assert len(await sim.open_orders()) == 1  # no new entry was sent
    before = len(await store.audit_entries())
    await runner.tick()  # same day: not processed twice
    assert len(await store.audit_entries()) == before


async def test_stop_updates_skip_missing_history_and_survive_broker_errors(store: Store) -> None:
    runner, _, market, _, _ = await make(store, DURING)
    await runner.start()
    await runner._engine.submit_entry(
        EntrySignal(
            signal_id="trend:AAPL:y",
            strategy="trend",
            instrument=AAPL,
            quantity=10,
            limit_price=D(100),
            stop_price=D(90),
            expected_edge=D(100),
            estimated_cost=D(5),
            explanation_sv="Test.",
        )
    )
    await runner.after_close(date(2026, 11, 16))  # no history: stop untouched
    assert (await store.known_order("trend:AAPL:y.stop")).stop_price == D(90)
    market.history = bars_rising(date(2026, 11, 16))

    async def broken(entry_id: str, level: Decimal) -> object:
        raise BrokerError("refused")

    runner._engine.raise_stop = broken  # type: ignore[method-assign,assignment]
    await runner.after_close(date(2026, 11, 16))
    assert (await store.known_order("trend:AAPL:y.stop")).stop_price == D(90)


async def test_reconnects_when_the_gateway_dropped(store: Store) -> None:
    runner, sim, *_ = await make(store, DURING)
    await runner.start()
    await sim.disconnect()
    await runner.tick()
    assert sim.is_connected()


async def test_gateway_still_down_keeps_trading_halted(store: Store) -> None:
    runner, sim, *_ = await make(store, DURING)
    await runner.start()
    sim.go_offline()
    assert not await runner.connect()
    await runner.tick()
    assert not runner._engine.health().positions_reconciled


async def test_calendar_gap_is_logged_not_guessed(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    runner, *_ = await make(store, datetime(2031, 6, 1, tzinfo=UTC))
    assert runner._close_due(datetime(2031, 6, 1, tzinfo=UTC)) is None
    assert "does not cover" in caplog.text
    assert runner._close_due(datetime(2026, 11, 14, 22, tzinfo=UTC)) is None  # Saturday


async def test_run_loops_until_stopped_and_survives_errors(store: Store) -> None:
    runner, _, _, _, pauses = await make(store, DURING)
    stop = asyncio.Event()
    calls = 0
    original = runner.tick

    async def tick() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        await original()
        stop.set()

    runner.tick = tick  # type: ignore[method-assign]
    await runner.run(stop)
    assert calls == 2
    assert pauses.count(60.0) == 2


TUESDAY_OPEN = datetime(2026, 11, 17, 14, 35, tzinfo=UTC)  # 5 min after the open
TUESDAY_LATER = datetime(2026, 11, 17, 14, 45, tzinfo=UTC)  # after the 10-min window


async def approve(store: Store, edge_r: float = 0.5) -> None:
    from jarvis.strategy.trend import params_dict

    await store.save_validation(
        "trend",
        params=params_dict(PARAMS),
        passed=True,
        edge_r=edge_r,
        report_sv="Godkänd.",
        at=DURING,
    )


async def test_approved_setup_is_entered_once_at_the_next_session(store: Store) -> None:
    runner, sim, market, clock, _ = await make(store, DURING)
    await runner.start()
    await approve(store)
    market.history = bars_rising(date(2026, 11, 16))
    sim.set_price("AAPL", D(105))
    market.prices["AAPL"] = D(105)
    clock.now = AFTER
    await runner.tick()
    assert len(runner.pending) == 1
    clock.now = TUESDAY_OPEN
    await runner.tick()
    assert len(runner.pending) == 1  # still inside the opening minutes
    clock.now = TUESDAY_LATER
    await runner.tick()
    assert runner.pending == []
    entry = await store.known_order("trend:AAPL:2026-11-16")
    assert entry.quantity > 0
    assert entry.limit_price == D("105.21")
    decision = await store.risk_decisions("trend:AAPL:2026-11-16")
    assert decision == [(True, [])]


async def test_unapproved_or_failed_validation_never_buys(store: Store) -> None:
    runner, _sim, market, clock, _ = await make(store, DURING)
    await runner.start()
    await store.save_validation(
        "trend", params=None, passed=False, edge_r=0.0, report_sv="Underkänd.", at=DURING
    )
    market.history = bars_rising(date(2026, 11, 16))
    clock.now = AFTER
    await runner.tick()
    assert runner.pending == []
    assert await store.order("trend:AAPL:2026-11-16") is None


async def test_queued_setups_lapse_after_one_session(store: Store) -> None:
    runner, _, market, _clock, _ = await make(store, DURING)
    await runner.start()
    await approve(store)
    market.history = bars_rising(date(2026, 11, 16))
    await runner.after_close(date(2026, 11, 16))
    assert runner.pending
    market.history = []
    await runner.after_close(date(2026, 11, 17))
    assert runner.pending == []


async def test_entry_is_skipped_without_quote_size_or_room(store: Store) -> None:
    runner, sim, market, _clock, _ = await make(store, TUESDAY_LATER)
    await runner.start()
    await approve(store)
    market.history = bars_rising(date(2026, 11, 16))
    await runner.after_close(date(2026, 11, 16))
    item = runner.pending[0]
    market.prices.pop("AAPL")
    await runner._enter(item)  # no quote
    market.prices["AAPL"] = D(50)
    await runner._enter(item)  # price already below the stop
    sim._cash = D(0)
    market.prices["AAPL"] = D(105)
    await runner._enter(item)  # nothing to buy with
    assert await store.order("trend:AAPL:2026-11-16") is None


async def test_a_failed_entry_does_not_stop_the_others(store: Store) -> None:
    runner, sim, market, _clock, _ = await make(store, TUESDAY_LATER)
    await runner.start()
    await approve(store)
    market.history = bars_rising(date(2026, 11, 16))
    await runner.after_close(date(2026, 11, 16))
    sim.fail_next_call(BrokerError("refused"))
    await runner.enter_pending()
    assert runner.pending == []


async def test_entry_window_outside_sessions(store: Store) -> None:
    runner, *_ = await make(store, DURING)
    assert not runner._entry_window_open(datetime(2026, 11, 14, 15, tzinfo=UTC))  # Saturday
    assert not runner._entry_window_open(datetime(2031, 6, 2, 15, tzinfo=UTC))  # no calendar


async def test_the_index_fund_close_is_recorded_after_the_close(store: Store) -> None:
    runner, _sim, market, clock, _ = await make(store, AFTER)
    await runner.start()
    spy = instrument("SPY", sector="index")
    runner._index_fund = spy
    market.prices["SPY"] = D("612.40")
    await runner.after_close(date(2026, 11, 16))
    assert await store.index_fund_values("SPY") == [(date(2026, 11, 16), D("612.40"))]
    del market.prices["SPY"]
    await runner.after_close(date(2026, 11, 17))  # no quote: nothing is invented
    assert len(await store.index_fund_values("SPY")) == 1
