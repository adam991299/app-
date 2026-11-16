from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from jarvis.economics.performance import MIN_DAYS_FOR_VERDICT, Comparison, compare, verdict_sv

D = Decimal
START = date(2026, 11, 2)
NAME = "S&P 500-fonden (SPY)"


def days(values: list[str], skip: set[int] | None = None) -> list[tuple[date, Decimal]]:
    return [
        (START + timedelta(days=i), D(v)) for i, v in enumerate(values) if i not in (skip or set())
    ]


def test_both_series_are_rebased_on_the_shared_days() -> None:
    result = compare(days(["50", "51", "52", "55"], skip={1}), days(["400", "404", "408", "396"]))
    assert result is not None
    assert [p.day for p in result.points] == [START, START + timedelta(2), START + timedelta(3)]
    assert result.points[0].jarvis == result.points[0].index == 100
    assert (result.jarvis_pct, result.index_pct) == (D(10), D(-1))
    assert result.difference_pct == D(11)
    assert result.days == 3


def test_no_comparison_without_two_shared_days_or_with_bad_values() -> None:
    assert compare(days(["50"]), days(["400", "401"])) is None
    assert compare([], []) is None
    assert compare(days(["0", "1"]), days(["400", "401"])) is None
    assert compare(days(["1", "1"]), days(["0", "401"])) is None


def comparison(jarvis_end: str, n: int = MIN_DAYS_FOR_VERDICT) -> Comparison:
    jarvis = ["100"] * (n - 1) + [jarvis_end]
    result = compare(days(jarvis), days(["100"] * (n - 1) + ["104"]))
    assert result is not None
    return result


def test_verdicts_are_honest() -> None:
    assert "inte tillräckligt med data" in verdict_sv(None, NAME)
    assert "för tidigt" in verdict_sv(comparison("110", n=5), NAME)
    assert verdict_sv(comparison("110"), NAME) == (
        "Jag ligger 6,00 procentenheter före S&P 500-fonden (SPY) efter kostnader."
    )
    behind = verdict_sv(comparison("101.5"), NAME)
    assert behind.startswith("Jag ligger 2,50 procentenheter efter")
    assert "bättre att bara äga indexfonden" in behind
    assert verdict_sv(comparison("104"), NAME) == (
        "Jag ligger lika med S&P 500-fonden (SPY) efter kostnader."
    )
