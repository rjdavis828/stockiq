"""Add alert_events table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alert_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.BigInteger(), nullable=False),
        sa.Column("triggered_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("bar_snapshot", JSONB(), nullable=True),
        sa.Column("notified_ws", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notified_email", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("alert_events")
