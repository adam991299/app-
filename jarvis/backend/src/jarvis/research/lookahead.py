"""Lookahead detection (spec §6.3 item 2).

A decision for day ``i`` may only depend on bars up to and including ``i``. The check
recomputes the series from a history that ends at ``i`` and compares it with the value
computed from the full history: any difference means the code looked into the future.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from jarvis.strategy.bars import Bar

SeriesFn = Callable[[list[Bar]], Sequence[Any]]


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    return bool(a == b)


def find_lookahead(series: SeriesFn, bars: list[Bar], days: Iterable[int]) -> list[int]:
    """The days whose value changes when the future is removed (empty means clean)."""
    full = series(bars)
    return [i for i in days if not _same(series(bars[: i + 1])[i], full[i])]
