"""Research trials and validation results (spec §6.3 items 9 and the lifecycle in §6.4).

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_trials",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("strategy", sa.String(64), nullable=False, index=True),
        sa.Column("params", postgresql.JSONB, nullable=False),
        sa.Column("sample", sa.String(16), nullable=False),
        sa.Column("window", sa.Integer, nullable=False),
        sa.Column("sharpe", sa.Float, nullable=False),
        sa.Column("trades", sa.Integer, nullable=False),
    )
    op.create_table(
        "validations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("strategy", sa.String(64), nullable=False, index=True),
        sa.Column("params", postgresql.JSONB),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("edge_r", sa.Float, nullable=False),
        sa.Column("report_sv", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("validations")
    op.drop_table("research_trials")
