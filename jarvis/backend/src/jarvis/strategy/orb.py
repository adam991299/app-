"""Opening range breakout, the day-trading strategy (spec §6.2.1). Long only.

Why it might work: the first minutes absorb the night's news and orders; a break above that
range on volume tends to continue for a while as late buyers chase. It often fails, so the
stop sits at the other side of the range and every position is closed before the close.

Rules on 5-minute bars of one session, using only bars that have finished:
- Opening range: the first ``range_minutes`` of the session.
- Entry: a bar closes above the range high, no later than ``last_entry_minutes`` before the
  close; the entry is at the next bar's open.
- Stop: the range low. Target: entry + ``target_r`` times (entry - stop).
- Exit: stop or target, or at the open of the bar starting ``flat_minutes`` before the close.
- At most one trade per symbol per day.

Two free parameters: ``range_minutes`` and ``target_r``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

NAME = "orb"
BAR = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class IntradayBar:
    at: datetime  # bar start, UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self) -> None:
        if self.at.utcoffset() is None:
            raise ValueError("bar time must be timezone-aware")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("bar prices must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("bar high/low do not contain open/close")

    @property
    def day(self) -> date:
        return self.at.date()


@dataclass(frozen=True, slots=True)
class OrbParameters:
    range_minutes: int = 15
    target_r: Decimal = Decimal(2)
    last_entry_minutes: int = 60
    flat_minutes: int = 15

    def __post_init__(self) -> None:
        if self.range_minutes < 5 or self.range_minutes % 5:
            raise ValueError("the opening range is a whole number of 5-minute bars")
        if self.target_r <= 0:
            raise ValueError("target_r must be positive")
        if self.flat_minutes < 5 or self.last_entry_minutes <= self.flat_minutes:
            raise ValueError("entries must stop before the positions are closed")

    @property
    def range_bars(self) -> int:
        return self.range_minutes // 5


@dataclass(frozen=True, slots=True)
class OrbSetup:
    signal_at: datetime  # start of the bar that broke out
    range_high: Decimal
    range_low: Decimal

    def target(self, entry: Decimal, params: OrbParameters) -> Decimal:
        return entry + params.target_r * (entry - self.range_low)


def setup_for(
    session: list[IntradayBar], close: datetime, params: OrbParameters
) -> OrbSetup | None:
    """The first breakout of the day among the bars given (all finished), or None."""
    if len(session) <= params.range_bars:
        return None
    opening = session[: params.range_bars]
    high = max(b.high for b in opening)
    low = min(b.low for b in opening)
    latest_end = close - timedelta(minutes=params.last_entry_minutes)
    for bar in session[params.range_bars :]:
        if bar.at + BAR > latest_end:
            return None
        if bar.close > high:
            return OrbSetup(bar.at, high, low)
    return None


def flat_time(close: datetime, params: OrbParameters) -> datetime:
    return close - timedelta(minutes=params.flat_minutes)
