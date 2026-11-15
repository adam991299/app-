"""Daily price bars. A bar is only ever used after its session has closed (no lookahead)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise


@dataclass(frozen=True, slots=True)
class Bar:
    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self) -> None:
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("bar prices must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("bar high/low do not contain open/close")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")


def validate_series(bars: list[Bar]) -> None:
    """Bars must be strictly ascending by day: duplicates or disorder mean bad data."""
    for previous, current in pairwise(bars):
        if current.day <= previous.day:
            raise ValueError(f"bars out of order or duplicated at {current.day.isoformat()}")
