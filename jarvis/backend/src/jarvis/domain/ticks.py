"""Price increments (ticks). Brokers reject prices between ticks, so every price Jarvis
sends is rounded first, in the direction that never increases risk.

US stocks trade in whole cents at or above 1 USD and in 0.0001 below it (SEC Rule 612).
Other markets have their own tables; they are added with those markets (Fas 1).
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

CENT = Decimal("0.01")
SUB_PENNY = Decimal("0.0001")


def tick_size(price: Decimal) -> Decimal:
    return CENT if price >= 1 else SUB_PENNY


def round_down(price: Decimal) -> Decimal:
    """For buy limits and new trailing stops: never pay more or stop out above the plan."""
    return price.quantize(tick_size(price), rounding=ROUND_FLOOR)


def round_up(price: Decimal) -> Decimal:
    """For initial stops and targets: the stop moves closer (less risk), never farther."""
    rounded = price.quantize(tick_size(price), rounding=ROUND_CEILING)
    return rounded.quantize(tick_size(rounded), rounding=ROUND_CEILING)


def on_tick(price: Decimal) -> bool:
    return price == round_down(price)
