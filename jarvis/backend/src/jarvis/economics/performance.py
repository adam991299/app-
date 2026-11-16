"""The honest comparison (§1.5, §0 rule 7): Jarvis's trading result against simply holding
the index fund over the same days, both in the base currency.

Jarvis is measured with the time-weighted index from the equity snapshots, so deposits and
withdrawals do not count as results. The index fund is valued in the base currency with the
day's exchange rate, so currency moves count for both.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

HUNDRED = Decimal(100)
MIN_DAYS_FOR_VERDICT = 20  # fewer trading days say nothing about skill


@dataclass(frozen=True, slots=True)
class Point:
    day: date
    jarvis: Decimal  # 100 at the start
    index: Decimal  # 100 at the start


@dataclass(frozen=True, slots=True)
class Comparison:
    points: list[Point]
    jarvis_pct: Decimal  # change since the start
    index_pct: Decimal

    @property
    def days(self) -> int:
        return len(self.points)

    @property
    def difference_pct(self) -> Decimal:
        """Percentage points by which Jarvis is ahead (+) or behind (-)."""
        return self.jarvis_pct - self.index_pct


def compare(
    trading: Sequence[tuple[date, Decimal]], index: Sequence[tuple[date, Decimal]]
) -> Comparison | None:
    """Both series on the days they share, each rebased to 100. None with fewer than two
    shared days."""
    values = dict(trading)
    shared = [(day, values[day], close) for day, close in index if day in values]
    if len(shared) < 2 or shared[0][1] <= 0 or shared[0][2] <= 0:
        return None
    _, jarvis_start, index_start = shared[0]
    points = [
        Point(day, j / jarvis_start * HUNDRED, i / index_start * HUNDRED) for day, j, i in shared
    ]
    return Comparison(points, points[-1].jarvis - HUNDRED, points[-1].index - HUNDRED)


def verdict_sv(comparison: Comparison | None, index_name_sv: str) -> str:
    if comparison is None:
        return (
            f"Jag har ännu inte tillräckligt med data för att jämföra mig med {index_name_sv}. "
            "Jämförelsen börjar när jag har följt kontot i minst två handelsdagar."
        )
    gap = _pct_sv(abs(comparison.difference_pct))
    if comparison.days < MIN_DAYS_FOR_VERDICT:
        return (
            f"Efter {comparison.days} handelsdagar är det för tidigt att säga om jag slår "
            f"{index_name_sv}. Siffrorna nedan visar läget hittills."
        )
    if comparison.difference_pct > 0:
        return f"Jag ligger {gap} procentenheter före {index_name_sv} efter kostnader."
    if comparison.difference_pct < 0:
        return (
            f"Jag ligger {gap} procentenheter efter {index_name_sv} efter kostnader. "
            "Just nu hade det varit bättre att bara äga indexfonden."
        )
    return f"Jag ligger lika med {index_name_sv} efter kostnader."


def _pct_sv(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")
