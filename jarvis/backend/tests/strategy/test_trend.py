from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from jarvis.strategy.bars import Bar, validate_series
from jarvis.strategy.trend import (
    TrendParameters,
    average_true_range,
    entry_setup,
    signal_id,
    trailing_stop,
)

D = Decimal
PARAMS = TrendParameters(entry_lookback=5, exit_lookback=3, atr_period=3, atr_stop_multiple=D(2))
START = date(2026, 1, 5)


def bar(i: int, close: str, *, high: str | None = None, low: str | None = None) -> Bar:
    c = D(close)
    return Bar(
        START + timedelta(days=i), c, D(high) if high else c + 1, D(low) if low else c - 1, c, 1000
    )


def flat(n: int, close: str = "100") -> list[Bar]:
    return [bar(i, close) for i in range(n)]


def test_bar_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        Bar(START, D(0), D(1), D(1), D(1), 0)
    with pytest.raises(ValueError, match="contain"):
        Bar(START, D(10), D(9), D(8), D(9), 0)
    with pytest.raises(ValueError, match="contain"):
        Bar(START, D(10), D(11), D(10.5), D(10), 0)
    with pytest.raises(ValueError, match="volume"):
        Bar(START, D(10), D(11), D(9), D(10), -1)


def test_series_must_be_ascending_without_duplicates() -> None:
    bars = flat(3)
    validate_series(bars)
    with pytest.raises(ValueError, match="out of order"):
        validate_series([bars[1], bars[0]])
    with pytest.raises(ValueError, match="out of order"):
        entry_setup([*flat(6), bar(5, "120")], PARAMS)
    with pytest.raises(ValueError, match="out of order"):
        trailing_stop([bars[0], bars[0]], PARAMS)


@pytest.mark.parametrize(
    "kwargs",
    [{"entry_lookback": 1}, {"exit_lookback": 0}, {"atr_period": 1}, {"atr_stop_multiple": D(0)}],
)
def test_parameter_validation(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"lookbacks|positive"):
        TrendParameters(**kwargs)  # type: ignore[arg-type]


def test_defaults_are_the_classic_55_20() -> None:
    params = TrendParameters()
    assert (params.entry_lookback, params.exit_lookback, params.bars_needed) == (55, 20, 56)


def test_atr() -> None:
    bars = [bar(0, "100"), bar(1, "100"), bar(2, "104"), bar(3, "104", high="110", low="103")]
    # true ranges: 2, max(2, 5, 3)=5, max(7, 6, 1)=7 -> mean 14/3
    assert average_true_range(bars, 3) == D(14) / 3
    with pytest.raises(ValueError, match="not enough"):
        average_true_range(bars, 4)


def test_breakout_gives_entry_with_atr_stop() -> None:
    bars = [*flat(6), bar(6, "103")]  # previous highs are 101
    setup = entry_setup(bars, PARAMS)
    assert setup is not None
    assert setup.reference_price == D(103)
    assert setup.channel_high == D(101)
    # true ranges of the last 3 bars: 2, 2, max(2, 4, 2)=4 -> ATR 8/3; stop 103 - 16/3
    assert setup.atr == D(8) / 3
    assert setup.stop_price == D(103) - D(16) / 3
    assert signal_id("AAPL", setup) == "trend:AAPL:2026-01-11"


def test_no_entry_without_breakout_or_history() -> None:
    assert entry_setup([*flat(6), bar(6, "101")], PARAMS) is None  # equal is not above
    assert entry_setup([*flat(4), bar(4, "150")], PARAMS) is None  # too little history
    assert entry_setup([], PARAMS) is None


def test_the_breakout_bar_is_not_part_of_its_own_channel() -> None:
    bars = [*flat(6), bar(6, "103", high="110")]
    assert entry_setup(bars, PARAMS) is not None  # its own high of 110 must not block it


def test_no_entry_when_the_stop_would_not_be_positive() -> None:
    wild = [bar(i, "10", high="40", low="1") for i in range(6)]
    assert entry_setup([*wild, bar(6, "41", high="42", low="1")], PARAMS) is None


def test_trailing_stop_is_lowest_recent_low() -> None:
    bars = [bar(0, "100", low="90"), bar(1, "105"), bar(2, "108"), bar(3, "110")]
    assert trailing_stop(bars, PARAMS) == D(104)  # the 90 has dropped out of the window
    assert trailing_stop(bars[:2], PARAMS) is None


prices = st.decimals(min_value=D(5), max_value=D(500), places=2)


@settings(max_examples=200)
@given(closes=st.lists(prices, min_size=7, max_size=40))
def test_decision_depends_only_on_the_recent_window(closes: list[Decimal]) -> None:
    """Older history must not leak in, and a setup always has its stop below the entry."""
    history = [bar(i, str(c)) for i, c in enumerate(closes)]
    decided = entry_setup(history, PARAMS)
    assert entry_setup(history[-PARAMS.bars_needed :], PARAMS) == decided
    assert trailing_stop(history, PARAMS) == trailing_stop(history[-PARAMS.exit_lookback :], PARAMS)
    if decided is not None:
        assert decided.stop_price < decided.reference_price
        assert decided.reference_price > decided.channel_high
