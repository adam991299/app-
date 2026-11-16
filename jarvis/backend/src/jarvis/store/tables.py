"""Database schema. Changes go through an Alembic migration in ``backend/migrations``."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MONEY = Numeric(24, 10)
UTC_TIME = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class Controls(Base):
    """Adam's switches. Exactly one row (id = 1), created by the first migration."""

    __tablename__ = "controls"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("trading_mode IN ('paper', 'live')", name="known_mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trading_mode: Mapped[str] = mapped_column(String(8), default="paper")
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    kill_switch_engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    kill_switch_reason: Mapped[str | None] = mapped_column(Text)
    peak_reset_at: Mapped[datetime | None] = mapped_column(UTC_TIME)
    risk_profile: Mapped[str] = mapped_column(String(16), server_default="balanced")
    previous_risk_profile: Mapped[str] = mapped_column(String(16), server_default="balanced")
    risk_profile_from: Mapped[datetime | None] = mapped_column(UTC_TIME)
    updated_at: Mapped[datetime] = mapped_column(UTC_TIME)


class EquitySnapshot(Base):
    """Account value as reported by the broker, recorded regularly. The circuit breakers'
    day/week lows and the peak are derived from these rows."""

    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTC_TIME, index=True)
    net_liquidation: Mapped[Decimal] = mapped_column(MONEY)
    cash: Mapped[Decimal] = mapped_column(MONEY)
    # net_liquidation minus all deposits/withdrawals so far: what trading alone produced
    adjusted: Mapped[Decimal] = mapped_column(MONEY)


class AuditEntry(Base):
    """Every settings change, login and manual action (§10)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTC_TIME, index=True)
    actor: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class RiskDecisionRow(Base):
    """Every risk check, approved or not, with the reasons (§7: "händelsen loggas")."""

    __tablename__ = "risk_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTC_TIME, index=True)
    client_order_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    approved: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    trading_state: Mapped[str] = mapped_column(String(16))


class OrderRow(Base):
    """Jarvis's journal of every order it created, from signal to final status (§8, §5.5.5)."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="known_side"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("kind IN ('entry', 'exit', 'stop', 'take_profit')", name="known_kind"),
        CheckConstraint(
            "status IN ('new', 'submitted', 'partially_filled', 'filled', 'cancelled', "
            "'rejected', 'expired')",
            name="known_status",
        ),
        CheckConstraint("filled_quantity >= 0 AND filled_quantity <= quantity", name="fill_range"),
    )

    client_order_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("orders.client_order_id"), index=True
    )
    strategy: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))  # entry, exit, stop, take_profit
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    currency: Mapped[str | None] = mapped_column(String(3))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    limit_price: Mapped[Decimal | None] = mapped_column(MONEY)
    stop_price: Mapped[Decimal | None] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(20), index=True)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    average_fill_price: Mapped[Decimal | None] = mapped_column(MONEY)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    explanation_sv: Mapped[str | None] = mapped_column(Text)
    signal: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTC_TIME)
    updated_at: Mapped[datetime] = mapped_column(UTC_TIME)


class FillRow(Base):
    """Executions as reported by the broker. ``fill_id`` is the broker's id: unique."""

    __tablename__ = "fills"
    __table_args__ = (CheckConstraint("quantity > 0", name="positive_quantity"),)

    fill_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("orders.client_order_id"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(MONEY)
    commission: Mapped[Decimal] = mapped_column(MONEY)
    at: Mapped[datetime] = mapped_column(UTC_TIME, index=True)


class AccountState(Base):
    """The latest picture of the account, written by execution after every
    reconciliation and read by the app. Exactly one row (id = 1)."""

    __tablename__ = "account_state"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(UTC_TIME)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ResearchTrial(Base):
    """Every backtest variant ever tried, failures included (§6.3 item 9)."""

    __tablename__ = "research_trials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTC_TIME, index=True)
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sample: Mapped[str] = mapped_column(String(16))
    window: Mapped[int] = mapped_column(Integer)
    sharpe: Mapped[float] = mapped_column(Float)
    trades: Mapped[int] = mapped_column(Integer)


class ValidationRow(Base):
    """The outcome of a full validation. Only a passed one lets a strategy trade."""

    __tablename__ = "validations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTC_TIME, index=True)
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    passed: Mapped[bool] = mapped_column(Boolean)
    edge_r: Mapped[float] = mapped_column(Float)
    report_sv: Mapped[str] = mapped_column(Text)


class CashFlow(Base):
    """A deposit (positive) or withdrawal (negative). Not profit or loss."""

    __tablename__ = "cash_flows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTC_TIME, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    note: Mapped[str] = mapped_column(Text)
