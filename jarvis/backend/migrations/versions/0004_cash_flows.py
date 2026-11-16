"""Deposits and withdrawals, and equity adjusted for them (so they are not profit or loss).

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(24, 10)


def upgrade() -> None:
    op.create_table(
        "cash_flows",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("note", sa.Text, nullable=False),
    )
    op.add_column("equity_snapshots", sa.Column("adjusted", MONEY))
    op.execute("UPDATE equity_snapshots SET adjusted = net_liquidation")
    op.alter_column("equity_snapshots", "adjusted", nullable=False)


def downgrade() -> None:
    op.drop_column("equity_snapshots", "adjusted")
    op.drop_table("cash_flows")
