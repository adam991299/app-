"""Synthetic price series for research tests (never shown as real data)."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from jarvis.strategy.bars import Bar
from jarvis.strategy.orb import IntradayBar


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


def orb_days(seed: int, days: int = 40, start: float = 100.0) -> list[IntradayBar]:
    """Random 5-minute bars for ``days`` NYSE sessions, 14:30-21:00 UTC (78 bars a day)."""
    rng = random.Random(seed)  # noqa: S311 - reproducible test data, not security
    out: list[IntradayBar] = []
    price = start
    day = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    while len({b.day for b in out}) < days:
        if day.weekday() < 5:
            for i in range(78):
                o = price
                price = max(1.0, price * (1 + rng.gauss(0.0001, 0.003)))
                hi, lo = max(o, price) * 1.001, min(o, price) * 0.999
                out.append(
                    IntradayBar(
                        day + i * timedelta(minutes=5),
                        Decimal(f"{o:.2f}"),
                        Decimal(f"{hi:.2f}"),
                        Decimal(f"{lo:.2f}"),
                        Decimal(f"{price:.2f}"),
                        10_000,
                    )
                )
        day += timedelta(days=1)
    return out
