"""Add unique constraint to fundamentals (ticker_id, period)

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_fundamentals_ticker_period",
        "fundamentals",
        ["ticker_id", "period"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_fundamentals_ticker_period", "fundamentals", type_="unique")
