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
- More trades in the same symbol the same day (at most ``MAX_TRADES_PER_SYMBOL``): after
  a trade has ended, a later bar must close above the highest price of the day so far. The
  stop stays at the range low.

Two free parameters: ``range_minutes`` and ``target_r``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

NAME = "orb"
BAR = timedelta(minutes=5)
MAX_TRADES_PER_SYMBOL = 3


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
    level: Decimal  # the price it closed above: the range high, or the day's high for a re-entry
    range_low: Decimal

    def target(self, entry: Decimal, params: OrbParameters) -> Decimal:
        return entry + params.target_r * (entry - self.range_low)


def setup_for(
    session: list[IntradayBar],
    close: datetime,
    params: OrbParameters,
    after: datetime | None = None,
) -> OrbSetup | None:
    """Whether the newest bar of ``session`` (all finished, one session) is a buy signal.

    Before the day's first trade in the symbol it must close above the range high. ``after``
    is when the previous trade ended: the bar must start after it and close above the day's
    high so far. The caller decides whether a trade is still allowed."""
    if len(session) <= params.range_bars:
        return None
    bar = session[-1]
    if bar.at + BAR > close - timedelta(minutes=params.last_entry_minutes):
        return None
    opening = session[: params.range_bars]
    low = min(b.low for b in opening)
    if after is None:
        level = max(b.high for b in opening)
    elif bar.at <= after:
        return None
    else:
        level = max(b.high for b in session[:-1])
    return OrbSetup(bar.at, level, low) if bar.close > level else None


def params_dict(params: OrbParameters) -> dict[str, object]:
    return {
        "range_minutes": str(params.range_minutes),
        "target_r": str(params.target_r),
        "last_entry_minutes": str(params.last_entry_minutes),
        "flat_minutes": str(params.flat_minutes),
    }


def params_from(data: dict[str, object]) -> OrbParameters:
    return OrbParameters(
        range_minutes=int(str(data["range_minutes"])),
        target_r=Decimal(str(data["target_r"])),
        last_entry_minutes=int(str(data["last_entry_minutes"])),
        flat_minutes=int(str(data["flat_minutes"])),
    )


def flat_time(close: datetime, params: OrbParameters) -> datetime:
    return close - timedelta(minutes=params.flat_minutes)
