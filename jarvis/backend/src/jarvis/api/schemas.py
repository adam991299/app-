"""API contract between the backend and the web app (shared interface, §00.4).

Rules:
- Money and prices are decimal strings (never JSON floats), in the stated currency.
- Times are ISO 8601 in UTC; the app converts to Adam's display timezone.
- Every user-facing text field ends in ``_sv`` and is already Swedish.
- Nothing here is ever filled with invented values: when data is missing the field is
  ``null`` (or the list empty) and the app shows a designed empty state.

The web app mirrors these types in ``web/lib/api.ts``; a test keeps them in sync.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer

Money = Annotated[Decimal, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReasonOut(_Schema):
    code: str
    message_sv: str


class MarketOut(_Schema):
    exchange: str  # MIC, e.g. XNYS
    name_sv: str  # e.g. "USA"
    is_open: bool
    opens_at: datetime | None  # today's (or the next) regular session
    closes_at: datetime | None


TradingStateOut = Literal[
    "active", "no_new_trades", "closing_only", "paused", "kill_switch", "halted"
]


class StatusOut(_Schema):
    """GET /api/status — what the orb and the briefing show."""

    mode: Literal["paper", "live"]
    trading_state: TradingStateOut
    reasons: list[ReasonOut]
    broker_connected: bool
    markets: list[MarketOut]
    briefing_sv: str  # one or two calm sentences built from the fields above
    as_of: datetime


class PositionOut(_Schema):
    symbol: str
    quantity: int
    currency: str
    average_price: Money
    last_price: Money | None
    market_value: Money | None  # base currency
    unrealized_pnl: Money | None  # base currency
    unrealized_pnl_pct: Money | None  # percent units, e.g. "1.25"
    stop_price: Money | None
    strategy: str | None


class PortfolioOut(_Schema):
    """GET /api/portfolio — the big number and the holdings."""

    base_currency: str
    net_liquidation: Money | None
    cash: Money | None
    day_change: Money | None
    day_change_pct: Money | None  # percent units
    positions: list[PositionOut]
    as_of: datetime


class TradeOut(_Schema):
    id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    price: Money
    commission: Money
    currency: str
    at: datetime
    strategy: str | None
    explanation_sv: str | None  # why Jarvis made the trade, from the journal


class TradesOut(_Schema):
    """GET /api/trades?limit=N — newest first."""

    trades: list[TradeOut]


class TodayOut(_Schema):
    """GET /api/today — the "Idag" row."""

    trades_count: int
    realized_pnl: Money | None  # base currency
    risk_level_sv: str  # e.g. "Balanserad"
