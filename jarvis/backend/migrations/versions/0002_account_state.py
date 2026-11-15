"""Account state snapshot for the app, and the currency of each order.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.CheckConstraint("id = 1", name="single_row"),
    )
    op.add_column("orders", sa.Column("currency", sa.String(3)))


def downgrade() -> None:
    op.drop_column("orders", "currency")
    op.drop_table("account_state")
