from __future__ import annotations

from decimal import Decimal

import pytest

from jarvis.domain.ticks import on_tick, round_down, round_up, tick_size

D = Decimal


@pytest.mark.parametrize(
    ("price", "down", "up"),
    [
        ("100.2049", "100.20", "100.21"),
        ("489", "489.00", "489.00"),
        ("0.123456", "0.1234", "0.1235"),
        ("0.99999", "0.9999", "1.00"),
    ],
)
def test_rounding_directions(price: str, down: str, up: str) -> None:
    assert round_down(D(price)) == D(down)
    assert round_up(D(price)) == D(up)


def test_tick_sizes_and_check() -> None:
    assert tick_size(D(1)) == D("0.01")
    assert tick_size(D("0.5")) == D("0.0001")
    assert on_tick(D("10.25"))
    assert not on_tick(D("10.255"))
