from __future__ import annotations

from datetime import timedelta

from jarvis.config.settings import Validation
from jarvis.research.costs import CostModel
from jarvis.research.validation import (
    Evaluation,
    common_dates,
    evaluate,
    report_sv,
    validate,
)
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import TrendParameters
from tests.research.data import random_walk

GRID = [
    TrendParameters(entry_lookback=20, exit_lookback=10, atr_period=14),
    TrendParameters(entry_lookback=40, exit_lookback=20, atr_period=14),
]
RULES = Validation()


def universe(drift: float, n: int = 900) -> dict[str, list[Bar]]:
    return {f"S{i}": random_walk(100 + i, n=n, drift=drift) for i in range(4)}


def test_noise_does_not_pass_and_the_report_says_so() -> None:
    series = universe(drift=0.0)
    report = validate(
        series, GRID, RULES, benchmark=random_walk(9, n=900), train_days=250, test_days=60
    )
    assert not report.passed
    text = report_sv("Trendföljning", report)
    assert "klarade INTE kraven" in text
    assert "underkänt" in text


def test_every_variant_tried_is_registered_and_holdout_used_once() -> None:
    series = universe(drift=0.001)
    report = validate(series, GRID, RULES, benchmark=None, train_days=250, test_days=60)
    in_sample = [t for t in report.trials if t.sample == "in"]
    out_sample = [t for t in report.trials if t.sample == "out"]
    holdout = [t for t in report.trials if t.sample == "holdout"]
    assert len(in_sample) == len(out_sample) * len(GRID)
    assert len(holdout) == 1
    assert report.chosen in GRID


def test_holdout_days_never_reach_the_walk_forward() -> None:
    series = universe(drift=0.001)
    report = validate(series, GRID, RULES, benchmark=None, train_days=250, test_days=60)
    days = common_dates(series)
    holdout_start = days[int(len(days) * 0.8)]
    assert max(report.out_of_sample.daily) < holdout_start
    assert min(report.holdout.daily) >= holdout_start


def test_without_benchmark_data_the_strategy_cannot_pass() -> None:
    report = validate(
        universe(drift=0.002), GRID, RULES, benchmark=None, train_days=250, test_days=60
    )
    benchmark = next(c for c in report.checks if c.key == "benchmark")
    assert not benchmark.passed
    assert benchmark.value is None
    assert not report.passed


def test_benchmark_comparison_runs_when_data_exists() -> None:
    report = validate(
        universe(drift=0.002),
        GRID,
        RULES,
        benchmark=random_walk(9, n=900, drift=-0.001),
        train_days=250,
        test_days=60,
    )
    benchmark = next(c for c in report.checks if c.key == "benchmark")
    assert benchmark.value is not None


def test_earlier_trials_make_the_bar_higher() -> None:
    series = universe(drift=0.002)
    alone = validate(series, GRID, RULES, benchmark=None, train_days=250, test_days=60)
    crowded = validate(
        series,
        GRID,
        RULES,
        benchmark=None,
        train_days=250,
        test_days=60,
        earlier_trial_sharpes=[0.01 * i for i in range(200)],
    )
    dsr = {c.key: c.value for c in alone.checks}["dsr"]
    crowded_dsr = {c.key: c.value for c in crowded.checks}["dsr"]
    assert crowded_dsr is not None
    assert dsr is not None
    assert crowded_dsr <= dsr


def test_too_little_history_fails_cleanly() -> None:
    short = universe(drift=0.001, n=100)
    report = validate(short, GRID, RULES, benchmark=None)
    assert not report.passed
    assert report.out_of_sample.trades == []
    assert report.edge_r == 0.0
    assert validate({}, GRID, RULES, benchmark=None).chosen is None


def test_evaluate_counts_only_the_window() -> None:
    series = universe(drift=0.001, n=300)
    days = common_dates(series)
    window = evaluate(series, GRID[0], days[150], days[199], CostModel())
    assert min(window.daily) >= days[150]
    assert max(window.daily) <= days[199]
    assert all(t.entry_index >= 0 for t in window.trades)
    assert Evaluation().returns == []
    assert days[1] - days[0] == timedelta(days=1)
