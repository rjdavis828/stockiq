"""add job_configs table

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_configs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(64), unique=True, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("universe_filter", sa.String(32), nullable=False, server_default="SP500"),
        sa.Column("cron_schedule", sa.String(128)),
        sa.Column("extra_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    # universe_filter for intraday/daily/fundamentals uses comma-separated exchange codes.
    # XNAS = NASDAQ, XNYS = NYSE. Set to ALL to disable filtering.
    op.execute("""
        INSERT INTO job_configs (job_name, enabled, universe_filter, cron_schedule, extra_config, updated_at)
        VALUES
            ('poll-intraday-bars', true, 'XNAS,XNYS', '*/15 9-16 * * mon-fri',
             '{"interval": "5m", "chunk_size": 100, "chunk_sleep": 5.0}'::jsonb, NOW()),
            ('ingest-daily-ohlcv', true, 'XNAS,XNYS', '30 18 * * *', '{}'::jsonb, NOW()),
            ('refresh-tickers', true, 'ALL', '0 6 * * mon-fri', '{}'::jsonb, NOW()),
            ('run-active-scans', true, 'ALL', '0 19 * * *', '{}'::jsonb, NOW()),
            ('ingest-fundamentals', true, 'XNAS,XNYS', '0 5 * * sun', '{}'::jsonb, NOW())
        ON CONFLICT (job_name) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("job_configs")
