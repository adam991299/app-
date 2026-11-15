from __future__ import annotations

import pytest

from jarvis.research.costs import CostModel
from jarvis.research.event_backtest import run_event, size
from jarvis.research.vector_backtest import run_vector
from jarvis.strategy.trend import TrendParameters
from tests.research.data import random_walk

PARAMS = TrendParameters(entry_lookback=20, exit_lookback=10, atr_period=14)


@pytest.mark.parametrize("seed", range(12))
def test_both_backtesters_agree(seed: int) -> None:
    """Fas 2 acceptance: the same strategy gives the same result in both backtesters."""
    bars = random_walk(seed, drift=0.001 if seed % 2 else -0.0005)
    event, vector = run_event(bars, PARAMS), run_vector(bars, PARAMS)
    assert len(event.trades) == len(vector.trades)
    for a, b in zip(event.trades, vector.trades, strict=True):
        assert (a.entry_index, a.exit_index, a.shares) == (b.entry_index, b.exit_index, b.shares)
        assert a.pnl == pytest.approx(b.pnl, rel=1e-9, abs=1e-6)
    assert event.equity == pytest.approx(vector.equity, rel=1e-9)


def test_trades_happen_and_costs_are_charged() -> None:
    bars = random_walk(3, drift=0.002)
    free = run_event(bars, PARAMS, costs=CostModel(0, 0, 100, 0, 0, 0))
    costly = run_event(bars, PARAMS)
    assert free.trades
    assert costly.equity[-1] < free.equity[-1]
    assert all(t.costs > 0 for t in costly.trades)


def test_size_respects_risk_and_position_caps() -> None:
    assert size(100_000, 100, 90, 0.75, 10) == 75  # risk binds: 750 / 10
    assert size(100_000, 100, 99.9, 0.75, 10) == 100  # position cap binds
    assert size(100_000, 100, 100, 0.75, 10) == 0


def test_cost_model() -> None:
    model = CostModel()
    assert model.commission(10, 100) == 1.0  # minimum
    assert model.commission(1000, 100) == 5.0
    assert model.commission(1000, 0.05) == 0.5  # capped at 1 % of value
    assert model.commission(0, 100) == 0.0
    assert model.total(0, 100, 1e6) == 0.0
    small = model.slippage_per_share(100, 100, 1_000_000)
    big = model.slippage_per_share(100, 40_000, 1_000_000)
    assert big > small > 0
    assert model.slippage_per_share(100, 1, 0) > big  # unknown volume: assume the worst
