"""Plain, immutable value types. Money and prices are always ``Decimal``, never float.

Amounts called "base" are in the account's base currency (SEK for Adam's ISK).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    COMMODITY = "commodity"
    CRYPTO = "crypto"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    exchange: str
    currency: str
    asset_class: AssetClass
    sector: str | None = None
    small_cap: bool = False

    def __post_init__(self) -> None:
        if not self.symbol or not self.exchange:
            raise ValueError("instrument needs a symbol and an exchange")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError(f"currency must be an ISO 4217 code, got {self.currency!r}")


@dataclass(frozen=True, slots=True)
class Quote:
    """Latest price for one instrument. ``fx_to_base`` converts its currency to base."""

    symbol: str
    last: Decimal
    fx_to_base: Decimal
    at: datetime

    def __post_init__(self) -> None:
        if self.last <= 0 or self.fx_to_base <= 0:
            raise ValueError("quote price and fx rate must be positive")
        if self.at.utcoffset() is None:
            raise ValueError("quote timestamp must be timezone-aware")

    @property
    def last_base(self) -> Decimal:
        return self.last * self.fx_to_base


@dataclass(frozen=True, slots=True)
class Position:
    """A long position (Jarvis is long-only, §3). ``stop_price`` is the broker-side stop."""

    instrument: Instrument
    quantity: int
    average_price: Decimal
    stop_price: Decimal | None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("a position must have a positive quantity")
        if self.average_price <= 0:
            raise ValueError("average price must be positive")


@dataclass(frozen=True, slots=True)
class Account:
    """Account totals in base currency, as reported by the broker."""

    net_liquidation: Decimal
    cash: Decimal
