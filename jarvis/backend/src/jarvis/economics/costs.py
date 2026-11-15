"""Fixed costs and the break-even return (§1.5)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class BreakEven:
    monthly_costs: Decimal
    yearly_costs: Decimal
    required_return_pct: Decimal  # per year, just to cover the costs
    warning: bool  # above the configured limit: suggest cheaper data or fewer markets


def break_even(
    monthly_costs: Mapping[str, Decimal], capital: Decimal, warning_pct: Decimal
) -> BreakEven:
    """Example from the spec: 2 000 kr/month on 100 000 kr capital needs 24 % a year."""
    if capital <= 0:
        raise ValueError("capital must be positive")
    if any(cost < 0 for cost in monthly_costs.values()):
        raise ValueError("a cost cannot be negative")
    monthly = sum(monthly_costs.values(), Decimal(0))
    yearly = monthly * 12
    required = yearly / capital * HUNDRED
    return BreakEven(monthly, yearly, required, required > warning_pct)
