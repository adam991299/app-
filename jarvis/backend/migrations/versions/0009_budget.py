"""Jarvis budget (§7.1): the share of the account Jarvis may manage, with the time a raise
takes effect.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "controls", sa.Column("budget_pct", sa.Float(), nullable=False, server_default="100")
    )
    op.add_column(
        "controls",
        sa.Column("previous_budget_pct", sa.Float(), nullable=False, server_default="100"),
    )
    op.add_column("controls", sa.Column("budget_from", sa.DateTime(timezone=True)))
    op.create_check_constraint("budget_range", "controls", "budget_pct > 0 AND budget_pct <= 100")


def downgrade() -> None:
    op.drop_constraint("budget_range", "controls")
    op.drop_column("controls", "budget_from")
    op.drop_column("controls", "previous_budget_pct")
    op.drop_column("controls", "budget_pct")
