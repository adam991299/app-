"""Position sizing (spec §7 "Per affär" and "Gap- och extremrisk").

The quantity is the smallest of four limits, so every one of them holds:
1. risk to the stop ≤ ``max_risk_pct`` of equity,
2. position value ≤ the position cap for the asset class,
3. loss in the gap scenario ≤ ``max_gap_loss_pct`` of equity,
4. the cash that is free above the cash reserve.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum

from jarvis.config.settings import Risk
from jarvis.domain import AssetClass, Instrument
from jarvis.risk.units import fraction


class SizingLimit(StrEnum):
    TRADE_RISK = "trade_risk"
    POSITION_CAP = "position_cap"
    GAP_LOSS = "gap_loss"
    CASH = "cash"


@dataclass(frozen=True, slots=True)
class SizingResult:
    quantity: int
    binding_limit: SizingLimit


def position_cap_fraction(instrument: Instrument, risk: Risk) -> Decimal:
    portfolio = risk.portfolio
    if instrument.asset_class is AssetClass.CRYPTO:
        cap = portfolio.max_position_crypto_pct
    elif instrument.small_cap:
        cap = portfolio.max_position_small_cap_pct
    else:
        cap = portfolio.max_position_pct
    return min(fraction(cap), fraction(risk.technical_max.single_stock_pct_of_budget))


def gap_fraction(instrument: Instrument, risk: Risk) -> Decimal:
    if instrument.asset_class is AssetClass.CRYPTO:
        return fraction(risk.gap.crypto_gap_pct)
    return fraction(risk.gap.single_stock_gap_pct)


def gap_loss_per_unit(entry: Decimal, stop: Decimal, gap: Decimal) -> Decimal:
    """Loss per unit if price gaps down: the gap move, or the stop distance if larger."""
    return max(entry * gap, entry - stop)


def _floor(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def size_position(
    *,
    instrument: Instrument,
    equity: Decimal,
    free_cash: Decimal,
    entry: Decimal,
    stop: Decimal,
    fx_to_base: Decimal,
    risk: Risk,
) -> SizingResult:
    """Largest whole quantity that respects every per-trade limit (prices in quote
    currency, equity and free cash in base currency)."""
    if entry <= 0 or fx_to_base <= 0:
        raise ValueError("entry price and fx rate must be positive")
    if not 0 < stop < entry:
        raise ValueError("stop must be positive and below the entry price (long only)")
    if equity <= 0:
        return SizingResult(0, SizingLimit.CASH)

    entry_base = entry * fx_to_base
    limits = {
        SizingLimit.TRADE_RISK: equity
        * fraction(risk.per_trade.max_risk_pct)
        / ((entry - stop) * fx_to_base),
        SizingLimit.POSITION_CAP: equity * position_cap_fraction(instrument, risk) / entry_base,
        SizingLimit.GAP_LOSS: equity
        * fraction(risk.gap.max_gap_loss_pct)
        / (gap_loss_per_unit(entry, stop, gap_fraction(instrument, risk)) * fx_to_base),
        SizingLimit.CASH: max(free_cash, Decimal(0)) / entry_base,
    }
    binding = min(limits, key=lambda name: limits[name])
    return SizingResult(max(_floor(limits[binding]), 0), binding)
