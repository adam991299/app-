"""Trend following on daily bars: a Donchian channel breakout with an ATR stop (§6.1).

Why the edge might exist: prices of assets under sustained buying tend to keep drifting
(investors under-react to news and herd late); the other side of the trade is sellers
taking profit early. The strategy loses small and often in sideways markets and needs a
few large trends to pay for it. Whether it survives costs must be shown by the
validation in §6.3; nothing here assumes it does.

Rules, using only bars whose sessions have closed:
- **Entry:** the latest close is above the highest high of the previous
  ``entry_lookback`` days (the latest bar itself excluded).
- **Initial stop:** entry reference minus ``atr_stop_multiple`` times ATR(``atr_period``).
- **Exit:** a trailing stop at the lowest low of the latest ``exit_lookback`` days. It is
  only ever raised; execution refuses to lower a stop.

Four free parameters (§6.3 item 10 allows at most five).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from jarvis.strategy.bars import Bar, validate_series

NAME = "trend"


@dataclass(frozen=True, slots=True)
class TrendParameters:
    entry_lookback: int = 55
    exit_lookback: int = 20
    atr_period: int = 20
    atr_stop_multiple: Decimal = Decimal(2)

    def __post_init__(self) -> None:
        if min(self.entry_lookback, self.exit_lookback, self.atr_period) < 2:
            raise ValueError("lookbacks must be at least 2 days")
        if self.atr_stop_multiple <= 0:
            raise ValueError("atr_stop_multiple must be positive")

    @property
    def bars_needed(self) -> int:
        return max(self.entry_lookback, self.exit_lookback, self.atr_period) + 1


@dataclass(frozen=True, slots=True)
class EntrySetup:
    """A breakout seen on the latest closed bar. Prices are in the instrument's currency."""

    day: str  # ISO date of the bar that broke out; part of the signal id
    reference_price: Decimal  # the breakout bar's close
    channel_high: Decimal
    stop_price: Decimal
    atr: Decimal


def average_true_range(bars: list[Bar], period: int) -> Decimal:
    """Simple mean of the true range over the latest ``period`` bars."""
    if len(bars) < period + 1:
        raise ValueError("not enough bars for the ATR")
    ranges = []
    for previous, current in zip(bars[-period - 1 : -1], bars[-period:], strict=True):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return sum(ranges, Decimal(0)) / period


def entry_setup(bars: list[Bar], params: TrendParameters) -> EntrySetup | None:
    """The entry for the latest closed bar, or None. Too little history means no entry."""
    validate_series(bars)
    if len(bars) < params.bars_needed:
        return None
    latest = bars[-1]
    channel_high = max(bar.high for bar in bars[-params.entry_lookback - 1 : -1])
    if latest.close <= channel_high:
        return None
    atr = average_true_range(bars, params.atr_period)
    stop = latest.close - params.atr_stop_multiple * atr
    if atr <= 0 or stop <= 0:
        return None
    return EntrySetup(
        day=latest.day.isoformat(),
        reference_price=latest.close,
        channel_high=channel_high,
        stop_price=stop,
        atr=atr,
    )


def trailing_stop(bars: list[Bar], params: TrendParameters) -> Decimal | None:
    """Where the exit stop should be at least: the lowest low of the latest
    ``exit_lookback`` closed bars. None when there is too little history."""
    validate_series(bars)
    if len(bars) < params.exit_lookback:
        return None
    return min(bar.low for bar in bars[-params.exit_lookback :])


def signal_id(symbol: str, setup: EntrySetup) -> str:
    """Deterministic: replaying the same bar gives the same id, so never a second order."""
    return f"{NAME}:{symbol}:{setup.day}"
