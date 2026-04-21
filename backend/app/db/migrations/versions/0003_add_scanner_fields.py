"""Add scanner user_id, description, last_run columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("user_id", sa.String(64), nullable=False, server_default=""))
    op.add_column("scans", sa.Column("description", sa.Text))
    op.add_column("scans", sa.Column("last_run", sa.TIMESTAMP(timezone=True)))
    op.alter_column("scans", "user_id", server_default=None)


def downgrade() -> None:
    op.drop_column("scans", "last_run")
    op.drop_column("scans", "description")
    op.drop_column("scans", "user_id")
