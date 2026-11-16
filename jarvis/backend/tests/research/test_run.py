from __future__ import annotations

from datetime import UTC, date, datetime

from jarvis.config.settings import Validation
from jarvis.domain import Instrument
from jarvis.research.run import BENCHMARK, run_orb_validation, run_validation
from jarvis.store.repo import Store
from jarvis.strategy.bars import Bar
from jarvis.strategy.orb import IntradayBar, OrbParameters
from jarvis.strategy.trend import TrendParameters, params_dict, params_from
from tests.factories import instrument
from tests.research.data import orb_days, random_walk

NOW = datetime(2026, 11, 16, 22, tzinfo=UTC)
GRID = [TrendParameters(entry_lookback=20, exit_lookback=10, atr_period=14)]


class Market:
    def __init__(self, benchmark: bool = True) -> None:
        self.benchmark = benchmark

    async def quote(self, inst: Instrument) -> None:
        return None

    async def daily_bars(self, inst: Instrument, *, years: int, closed_through: date) -> list[Bar]:
        if inst == BENCHMARK:
            return random_walk(99, n=700) if self.benchmark else []
        return random_walk(hash(inst.symbol) % 1000, n=700, drift=0.001)

    async def instrument(self, symbol: str, currency: str = "USD") -> Instrument | None:
        return None if symbol == "GONE" else instrument(symbol)


def test_params_round_trip() -> None:
    params = TrendParameters(entry_lookback=55, exit_lookback=20, atr_period=20)
    assert params_from(params_dict(params)) == params


async def test_run_records_every_trial_and_the_verdict(store: Store) -> None:
    report, text = await run_validation(
        market=Market(),
        store=store,
        symbols=["AAA", "BBB", "GONE"],
        rules=Validation(),
        clock=lambda: NOW,
        grid=GRID,
    )
    assert "Data: 2 aktier" in text
    assert len(await store.trial_sharpes("trend")) == sum(t.sample == "in" for t in report.trials)
    saved = await store.latest_validation("trend")
    assert saved is not None
    assert saved[0] == report.passed
    assert saved[3] == text


async def test_without_index_data_the_run_cannot_approve(store: Store) -> None:
    report, _ = await run_validation(
        market=Market(benchmark=False),
        store=store,
        symbols=["AAA"],
        rules=Validation(),
        clock=lambda: NOW,
        grid=GRID,
    )
    assert not report.passed


class IntradayMarket(Market):
    async def intraday_bars(
        self, inst: Instrument, *, now: datetime, days: int = 1
    ) -> list[IntradayBar]:
        return orb_days(hash(inst.symbol) % 1000, days=40)


async def test_orb_run_records_its_own_trials_and_verdict(store: Store) -> None:
    report, text = await run_orb_validation(
        market=IntradayMarket(),
        store=store,
        symbols=["AAA", "GONE"],
        rules=Validation(),
        clock=lambda: NOW,
        grid=[OrbParameters()],
        days=40,
    )
    assert "Data: 1 aktier, 40 handelsdagar" in text
    saved = await store.latest_validation("orb")
    assert saved is not None
    assert saved[0] == report.passed
    assert len(await store.trial_sharpes("orb")) == sum(t.sample == "in" for t in report.trials)
    assert await store.latest_validation("trend") is None
