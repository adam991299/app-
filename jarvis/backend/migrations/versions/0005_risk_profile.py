"""Risk level chosen by Adam, with the time it takes effect (raises wait a trading day).

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "controls",
        sa.Column("risk_profile", sa.String(16), nullable=False, server_default="balanced"),
    )
    op.add_column(
        "controls",
        sa.Column(
            "previous_risk_profile", sa.String(16), nullable=False, server_default="balanced"
        ),
    )
    op.add_column("controls", sa.Column("risk_profile_from", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("controls", "risk_profile_from")
    op.drop_column("controls", "previous_risk_profile")
    op.drop_column("controls", "risk_profile")
