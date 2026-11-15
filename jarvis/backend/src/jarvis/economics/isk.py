"""ISK tax (schablonbeskattning). The yearly figures come from Skatteverket via config and
are never hard-coded (§1.5); without them no tax is computed at all.

Capital base (kapitalunderlag) = (value at the start of each quarter + deposits during the
year) / 4. Above the tax-free level, the base is multiplied by the year's schablon rate.
This is a model for planning, not tax advice (§12).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from jarvis.config.settings import Tax

HUNDRED = Decimal(100)


class TaxFiguresMissingError(Exception):
    """This year's ISK figures are not in the config; Jarvis will not guess them."""


@dataclass(frozen=True, slots=True)
class IskTax:
    capital_base: Decimal
    taxable_base: Decimal
    tax: Decimal  # whole kronor


def isk_tax(quarter_values: Sequence[Decimal], deposits: Decimal, figures: Tax) -> IskTax:
    if figures.model != "isk":
        raise ValueError("the account is not taxed as an ISK in the config")
    if figures.isk_tax_free_level_sek is None or figures.isk_schablon_tax_pct is None:
        raise TaxFiguresMissingError("enter this year's ISK figures from Skatteverket")
    if len(quarter_values) != 4:
        raise ValueError("an ISK year has four quarter values")
    if deposits < 0 or any(v < 0 for v in quarter_values):
        raise ValueError("values and deposits cannot be negative")
    base = (sum(quarter_values, Decimal(0)) + deposits) / 4
    taxable = max(base - Decimal(str(figures.isk_tax_free_level_sek)), Decimal(0))
    tax = taxable * Decimal(str(figures.isk_schablon_tax_pct)) / HUNDRED
    return IskTax(base, taxable, tax.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def tax_drag_pct(capital: Decimal, figures: Tax) -> Decimal:
    """Yearly tax as a share of a steady capital: what the strategy must earn on top."""
    if capital <= 0:
        raise ValueError("capital must be positive")
    result = isk_tax([capital] * 4, Decimal(0), figures)
    return result.tax / capital * HUNDRED
