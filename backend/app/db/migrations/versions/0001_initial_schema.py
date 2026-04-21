"""initial schema with timescaledb hypertables

Revision ID: 0001
Revises:
Create Date: 2026-04-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TimescaleDB must be enabled before creating hypertables
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    op.create_table(
        "tickers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(16), unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("exchange", sa.String(20)),
        sa.Column("sector", sa.String(64)),
        sa.Column("industry", sa.String(128)),
        sa.Column("market_cap", sa.BigInteger),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "ohlcv_daily",
        sa.Column("ticker_id", sa.BigInteger, sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.Column("vwap", sa.Numeric(12, 4)),
        sa.Column("adj_close", sa.Numeric(12, 4)),
        sa.Column("source", sa.String(32)),
        sa.PrimaryKeyConstraint("ticker_id", "date"),
        sa.UniqueConstraint("ticker_id", "date", name="uq_ohlcv_daily_ticker_date"),
    )

    op.create_table(
        "ohlcv_intraday",
        sa.Column("ticker_id", sa.BigInteger, sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.Column("trade_count", sa.Integer),
        sa.Column("vwap", sa.Numeric(12, 4)),
        sa.PrimaryKeyConstraint("ticker_id", "ts", "timeframe"),
        sa.UniqueConstraint("ticker_id", "ts", "timeframe", name="uq_ohlcv_intraday_ticker_ts_tf"),
    )

    op.create_table(
        "scans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("conditions", JSONB, nullable=False),
        sa.Column("universe_filter", JSONB),
        sa.Column("logic", sa.String(8), default="AND", nullable=False),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "scanner_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("scan_id", sa.BigInteger, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker_id", sa.BigInteger, sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("condition_snapshot", JSONB),
        sa.Column("values_snapshot", JSONB),
    )

    op.create_table(
        "fundamentals",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ticker_id", sa.BigInteger, sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("revenue", sa.Numeric(20, 2)),
        sa.Column("eps", sa.Numeric(10, 4)),
        sa.Column("pe_ratio", sa.Numeric(10, 4)),
        sa.Column("market_cap", sa.BigInteger),
        sa.Column("reported_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("ticker_id", sa.BigInteger, sa.ForeignKey("tickers.id", ondelete="SET NULL")),
        sa.Column("scan_id", sa.BigInteger, sa.ForeignKey("scans.id", ondelete="SET NULL")),
        sa.Column("condition", JSONB, nullable=False),
        sa.Column("status", sa.String(16), default="active", nullable=False),
        sa.Column("notified_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    # Convert OHLCV tables to TimescaleDB hypertables
    op.execute(
        """
        SELECT create_hypertable(
            'ohlcv_daily', 'date',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        )
        """
    )
    op.execute(
        """
        SELECT create_hypertable(
            'ohlcv_intraday', 'ts',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
        """
    )

    # Indexes
    op.create_index("idx_ohlcv_daily_ticker_date", "ohlcv_daily", ["ticker_id", sa.text("date DESC")])
    op.create_index("idx_ohlcv_intra_ticker_ts", "ohlcv_intraday", ["ticker_id", sa.text("ts DESC")])
    op.create_index("idx_scan_results_scan", "scanner_results", ["scan_id", sa.text("triggered_at DESC")])
    op.create_index("idx_alerts_user", "alerts", ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("fundamentals")
    op.drop_table("scanner_results")
    op.drop_table("scans")
    op.drop_table("ohlcv_intraday")
    op.drop_table("ohlcv_daily")
    op.drop_table("tickers")
