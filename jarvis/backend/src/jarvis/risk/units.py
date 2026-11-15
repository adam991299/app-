"""Conversion of config percentages (floats in percent units) to exact fractions."""

from decimal import Decimal


def fraction(percent: float) -> Decimal:
    """0.75 (meaning 0.75 %) -> Decimal('0.0075'). Goes via str to avoid float artefacts."""
    return Decimal(str(percent)) / 100
