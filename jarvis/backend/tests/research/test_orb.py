from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from jarvis.config.settings import Validation
from jarvis.research.costs import CostModel
from jarvis.research.lookahead import find_lookahead
from jarvis.research.orb_backtest import evaluate_orb, run_orb
from jarvis.research.validation import validate
from jarvis.strategy.orb import IntradayBar, OrbParameters, flat_time, setup_for

D = Decimal
P = OrbParameters(range_minutes=15, target_r=D(2), last_entry_minutes=60, flat_minutes=15)
FREE = CostModel(0, 0, 100, 0, 0, 0)
OPEN = datetime(2026, 11, 16, 14, 30, tzinfo=UTC)


def bar(i: int, o: float, h: float, lo: float, c: float, day: datetime = OPEN) -> IntradayBar:
    return IntradayBar(
        day + timedelta(minutes=5 * i), D(str(o)), D(str(h)), D(str(lo)), D(str(c)), 1000
    )


def session(
    path: list[tuple[float, float, float, float]], day: datetime = OPEN
) -> list[IntradayBar]:
    """Opening range 99-101 in the first three bars, then the given bars, padded to 78."""
    bars = [
        bar(0, 100, 101, 99, 100, day),
        bar(1, 100, 100.5, 99.5, 100, day),
        bar(2, 100, 100.8, 99.2, 100, day),
    ]
    for o, h, lo, c in path:
        bars.append(bar(len(bars), o, h, lo, c, day))
    while len(bars) < 78:
        last = float(bars[-1].close)
        bars.append(bar(len(bars), last, last + 0.05, last - 0.05, last, day))
    return bars


def test_bar_and_parameter_validation() -> None:
    with pytest.raises(ValueError, match="timezone"):
        IntradayBar(datetime(2026, 1, 1), D(1), D(1), D(1), D(1), 0)  # noqa: DTZ001
    with pytest.raises(ValueError, match="positive"):
        bar(0, 0, 1, 1, 1)
    with pytest.raises(ValueError, match="contain"):
        bar(0, 10, 9, 8, 9)
    for kwargs in (
        {"range_minutes": 7},
        {"target_r": D(0)},
        {"flat_minutes": 3},
        {"last_entry_minutes": 10},
    ):
        with pytest.raises(ValueError, match=r"bars|positive|entries"):
            OrbParameters(**kwargs)
    assert P.range_bars == 3


def test_setup_found_on_the_first_breakout() -> None:
    bars = session([(100.5, 101.6, 100.4, 101.5)])
    close = bars[-1].at + timedelta(minutes=5)
    setup = setup_for(bars, close, P)
    assert setup is not None
    assert (setup.range_high, setup.range_low, setup.signal_at) == (D(101), D(99), bars[3].at)
    assert setup.target(D("101.5"), P) == D("101.5") + 2 * (D("101.5") - D(99))
    assert flat_time(close, P) == close - timedelta(minutes=15)
    assert setup_for(bars[:3], close, P) is None


def test_no_setup_without_breakout_or_too_late() -> None:
    quiet = session([])
    close = quiet[-1].at + timedelta(minutes=5)
    assert setup_for(quiet, close, P) is None
    late = session([(100, 100.1, 99.9, 100)] * 63 + [(100, 102, 100, 101.9)])
    assert setup_for(late, late[-1].at + timedelta(minutes=5), P) is None


def test_target_hit() -> None:
    bars = session(
        [(100.5, 101.6, 100.4, 101.5), (101.5, 101.6, 101.4, 101.5), (101.5, 107, 101.4, 106)]
    )
    result, days = run_orb(bars, P, costs=FREE)
    (trade,) = result.trades
    assert trade.entry_price == 101.5
    assert trade.exit_price == pytest.approx(101.5 + 2 * 2.5)
    assert trade.r_multiple == pytest.approx(2.0)
    assert days == [date(2026, 11, 16)]


def test_stop_hit_with_gap_fills_at_the_open() -> None:
    bars = session([(100.5, 101.6, 100.4, 101.5), (101.5, 101.6, 101.4, 101.5), (97, 97.5, 96, 97)])
    (trade,) = run_orb(bars, P, costs=FREE)[0].trades
    assert trade.exit_price == 97
    assert trade.r_multiple < -1  # the gap cost more than planned


def test_stop_before_target_in_the_same_bar() -> None:
    bars = session([(100.5, 101.6, 100.4, 101.5), (101.5, 107, 98, 101)])
    (trade,) = run_orb(bars, P, costs=FREE)[0].trades
    assert trade.exit_price == 99  # the worse case


def test_everything_is_closed_before_the_close() -> None:
    bars = session([(100.5, 101.6, 100.4, 101.5)])
    (trade,) = run_orb(bars, P, costs=FREE)[0].trades
    assert bars[trade.exit_index].at == bars[-1].at + timedelta(minutes=5) - timedelta(minutes=15)


def test_open_below_the_stop_means_no_entry_and_one_trade_per_day() -> None:
    gap = session([(100.5, 101.6, 100.4, 101.5), (98, 98.5, 97, 98), (101, 103, 101, 102.5)])
    assert run_orb(gap, P, costs=FREE)[0].trades == []


def test_stopped_on_the_entry_bar() -> None:
    bars = session([(100.5, 101.6, 100.4, 101.5), (101.5, 101.6, 98.5, 99)])
    (trade,) = run_orb(bars, P, costs=FREE)[0].trades
    assert (trade.entry_index, trade.exit_index, trade.exit_price) == (4, 4, 99)


def test_three_losses_in_a_row_sit_out_the_next_day() -> None:
    losing = [(100.5, 101.6, 100.4, 101.5), (101.5, 101.6, 101.4, 101.5), (97, 97.5, 96, 97)]
    days = [session(losing, OPEN + timedelta(days=d)) for d in range(5)]
    result, _ = run_orb([b for day in days for b in day], P, costs=FREE)
    assert len(result.trades) == 4  # days 1-3 lose, day 4 is skipped, day 5 trades


def random_days(seed: int, n: int, drift: float = 0.0) -> list[IntradayBar]:
    rng = random.Random(seed)  # noqa: S311 - reproducible test data
    bars, price = [], 100.0
    for d in range(n):
        day = OPEN + timedelta(days=d)
        for i in range(78):
            o = price
            c = o * (1 + rng.gauss(drift, 0.003))
            h, lo = (
                max(o, c) * (1 + abs(rng.gauss(0, 0.001))),
                min(o, c) * (1 - abs(rng.gauss(0, 0.001))),
            )
            bars.append(bar(i, round(o, 2), round(h, 2), round(lo, 2), round(c, 2), day))
            price = c
    return bars


def test_no_lookahead_in_the_setup() -> None:
    bars = random_days(5, 1)
    close = bars[-1].at + timedelta(minutes=5)

    def decisions(history: list[IntradayBar]) -> list[object]:
        return [setup_for(history[: i + 1], close, P) for i in range(len(history))]

    assert find_lookahead(decisions, bars, range(3, 60, 4)) == []


def test_orb_validation_runs_and_noise_fails() -> None:
    series = {s: random_days(seed, 160) for s, seed in (("A", 1), ("B", 2))}
    grid = [P, OrbParameters(range_minutes=30, target_r=D(3))]
    report = validate(
        series,
        grid,
        Validation(),
        benchmark=None,
        train_days=60,
        test_days=20,
        evaluator=evaluate_orb,
        free_parameters=2,
    )
    assert not report.passed
    assert report.chosen in grid
    assert {c.key: c.value for c in report.checks}["parameters"] == 2
    window = evaluate_orb(series, P, date(2030, 1, 1), date(2030, 1, 2), FREE)
    assert window.trades == []
