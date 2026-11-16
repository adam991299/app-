"""Daily close of the index fund Jarvis is compared with, valued in the base currency.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_fund_closes",
        sa.Column("symbol", sa.String(12), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("close", sa.Numeric(24, 10), nullable=False),
        sa.Column("fx_to_base", sa.Numeric(24, 10), nullable=False),
        sa.CheckConstraint("close > 0 AND fx_to_base > 0", name="positive_values"),
    )


def downgrade() -> None:
    op.drop_table("index_fund_closes")
