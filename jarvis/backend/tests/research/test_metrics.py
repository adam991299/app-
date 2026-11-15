from __future__ import annotations

import math

import pytest

from jarvis.research.event_backtest import Trade
from jarvis.research.metrics import (
    annualised_sharpe,
    deflated_sharpe,
    drawdown_quantile,
    expected_max_sharpe,
    max_drawdown,
    probabilistic_sharpe,
    profit_factor,
    returns,
    sharpe,
)


def trade(pnl: float) -> Trade:
    return Trade(0, 1, 1, 100.0, 100.0 + pnl, 0.0)


def test_returns_and_drawdown() -> None:
    assert returns([100, 110, 99]) == pytest.approx([0.1, -0.1])
    assert max_drawdown([100, 120, 90, 130, 117]) == pytest.approx(0.25)
    assert max_drawdown([]) == 0.0


def test_sharpe() -> None:
    assert sharpe([0.01]) == 0.0
    assert sharpe([0.01, 0.01, 0.01]) == 0.0  # no variation
    assert sharpe([0.02, 0.0]) == pytest.approx(1.0)
    assert annualised_sharpe([0.02, 0.0]) == pytest.approx(math.sqrt(252))


def test_profit_factor() -> None:
    assert profit_factor([trade(30), trade(-10), trade(-10)]) == pytest.approx(1.5)
    assert profit_factor([trade(5)]) == math.inf
    assert profit_factor([]) == 0.0


def test_probabilistic_sharpe_grows_with_evidence() -> None:
    good = [0.002, -0.001, 0.003, 0.0, 0.001] * 10
    assert probabilistic_sharpe(good) > 0.9
    assert probabilistic_sharpe(good[:5]) < probabilistic_sharpe(good)
    assert probabilistic_sharpe(good, benchmark=1.0) < probabilistic_sharpe(good)
    assert probabilistic_sharpe([0.1, 0.2]) == 0.0  # too short to judge
    assert probabilistic_sharpe([0.0, 0.0, 0.0, 0.0]) == 0.5  # no edge, no spread


def test_more_trials_demand_more() -> None:
    returns_ = [0.002, -0.001, 0.003, 0.0, 0.001] * 10
    few = deflated_sharpe(returns_, [0.1, 0.12])
    many = deflated_sharpe(returns_, [0.05 * i for i in range(40)])
    assert many < few
    assert expected_max_sharpe([0.3]) == 0.0
    assert expected_max_sharpe([0.1, 0.2, 0.3]) > 0


def test_monte_carlo_drawdown() -> None:
    trades = [trade(100), trade(-300), trade(200), trade(-50), trade(150)]
    q = drawdown_quantile(trades, 10_000)
    assert 0 < q <= 0.035
    assert drawdown_quantile([], 10_000) == 0.0
    assert drawdown_quantile(trades, 10_000, quantile=1.0) >= q
