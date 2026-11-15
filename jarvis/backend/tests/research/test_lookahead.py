"""Fas 2 acceptance: the lookahead test catches a deliberately planted error."""

from __future__ import annotations

import pandas as pd

from jarvis.research.lookahead import find_lookahead
from jarvis.research.vector_backtest import signal_frame
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import TrendParameters, entry_setup
from tests.research.data import random_walk

PARAMS = TrendParameters(entry_lookback=20, exit_lookback=10, atr_period=14)
BARS = random_walk(11, n=200, drift=0.001)
DAYS = range(PARAMS.bars_needed, len(BARS), 7)


def correct_signals(bars: list[Bar]) -> list[bool]:
    return [bool(x) for x in signal_frame(bars, PARAMS)["signal"]]


def correct_stops(bars: list[Bar]) -> list[float]:
    return [float(x) for x in signal_frame(bars, PARAMS)["signal_stop"]]


def planted_bug(bars: list[Bar]) -> list[bool]:
    """Judges today's breakout with *tomorrow's* close: the classic peek into the future."""
    frame = signal_frame(bars, PARAMS)
    closes = pd.Series([float(b.close) for b in bars])
    tomorrow = closes.shift(-1)
    return [bool(c > h) for c, h in zip(tomorrow, frame["channel_high"], strict=True)]


def test_the_real_signals_do_not_look_ahead() -> None:
    assert find_lookahead(correct_signals, BARS, DAYS) == []
    assert find_lookahead(correct_stops, BARS, DAYS) == []


def test_the_live_strategy_does_not_look_ahead() -> None:
    def live(bars: list[Bar]) -> list[object]:
        return [None] * (len(bars) - 1) + [entry_setup(bars, PARAMS)]

    for day in DAYS:  # each day judged on its own history only
        assert find_lookahead(live, BARS[: day + 1], [day]) == []


def test_a_planted_lookahead_is_caught() -> None:
    assert find_lookahead(planted_bug, BARS, range(PARAMS.bars_needed, len(BARS) - 1)) != []
