"""Initial schema: controls, equity snapshots, audit log, risk decisions, orders, fills.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MONEY = sa.Numeric(24, 10)
UTC_TIME = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "controls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trading_mode", sa.String(8), nullable=False),
        sa.Column("paused", sa.Boolean, nullable=False),
        sa.Column("kill_switch_engaged", sa.Boolean, nullable=False),
        sa.Column("kill_switch_reason", sa.Text),
        sa.Column("peak_reset_at", UTC_TIME),
        sa.Column("updated_at", UTC_TIME, nullable=False),
        sa.CheckConstraint("id = 1", name="single_row"),
        sa.CheckConstraint("trading_mode IN ('paper', 'live')", name="known_mode"),
    )
    # Jarvis always starts in paper trading (§0 rule 3).
    op.execute(
        "INSERT INTO controls (id, trading_mode, paused, kill_switch_engaged, updated_at) "
        "VALUES (1, 'paper', false, false, now())"
    )
    op.create_table(
        "equity_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", UTC_TIME, nullable=False, index=True),
        sa.Column("net_liquidation", MONEY, nullable=False),
        sa.Column("cash", MONEY, nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", UTC_TIME, nullable=False, index=True),
        sa.Column("actor", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False),
    )
    op.create_table(
        "risk_decisions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", UTC_TIME, nullable=False, index=True),
        sa.Column("client_order_id", sa.String(128), nullable=False, index=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("approved", sa.Boolean, nullable=False),
        sa.Column("reasons", postgresql.ARRAY(sa.String(64)), nullable=False),
        sa.Column("trading_state", sa.String(16), nullable=False),
    )
    op.create_table(
        "orders",
        sa.Column("client_order_id", sa.String(128), primary_key=True),
        sa.Column("parent_id", sa.String(128), sa.ForeignKey("orders.client_order_id"), index=True),
        sa.Column("strategy", sa.String(64)),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("limit_price", MONEY),
        sa.Column("stop_price", MONEY),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("filled_quantity", sa.Integer, nullable=False),
        sa.Column("average_fill_price", MONEY),
        sa.Column("reject_reason", sa.Text),
        sa.Column("explanation_sv", sa.Text),
        sa.Column("signal", postgresql.JSONB, nullable=False),
        sa.Column("created_at", UTC_TIME, nullable=False),
        sa.Column("updated_at", UTC_TIME, nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="known_side"),
        sa.CheckConstraint("quantity > 0", name="positive_quantity"),
        sa.CheckConstraint("kind IN ('entry', 'exit', 'stop', 'take_profit')", name="known_kind"),
        sa.CheckConstraint(
            "status IN ('new', 'submitted', 'partially_filled', 'filled', 'cancelled', "
            "'rejected', 'expired')",
            name="known_status",
        ),
        sa.CheckConstraint(
            "filled_quantity >= 0 AND filled_quantity <= quantity", name="fill_range"
        ),
    )
    op.create_table(
        "fills",
        sa.Column("fill_id", sa.String(128), primary_key=True),
        sa.Column(
            "client_order_id",
            sa.String(128),
            sa.ForeignKey("orders.client_order_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("commission", MONEY, nullable=False),
        sa.Column("at", UTC_TIME, nullable=False, index=True),
        sa.CheckConstraint("quantity > 0", name="positive_quantity"),
    )


def downgrade() -> None:
    for table in ("fills", "orders", "risk_decisions", "audit_log", "equity_snapshots"):
        op.drop_table(table)
    op.drop_table("controls")
