"""Synthetic price series for research tests (never shown as real data)."""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from jarvis.strategy.bars import Bar


def random_walk(seed: int, n: int = 400, start: float = 100.0, drift: float = 0.0004) -> list[Bar]:
    rng = random.Random(seed)  # noqa: S311 - reproducible test data, not security
    price = start
    bars = []
    day = date(2020, 1, 1)
    for _ in range(n):
        opened = price * (1 + rng.gauss(0, 0.004))
        close = opened * (1 + rng.gauss(drift, 0.015))
        high = max(opened, close) * (1 + abs(rng.gauss(0, 0.006)))
        low = min(opened, close) * (1 - abs(rng.gauss(0, 0.006)))
        o, h, lo, c = (Decimal(f"{x:.2f}") for x in (opened, high, low, close))
        bars.append(Bar(day, o, h, lo, c, 1_000_000))
        price = close
        day += timedelta(days=1)
    return bars
