from datetime import date, datetime
from decimal import Decimal

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(20))
    sector: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128))
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    daily_bars: Mapped[list["OHLCVDaily"]] = relationship(back_populates="ticker")
    intraday_bars: Mapped[list["OHLCVIntraday"]] = relationship(back_populates="ticker")
    scan_results: Mapped[list["ScannerResult"]] = relationship(back_populates="ticker")


class OHLCVDaily(Base):
    __tablename__ = "ohlcv_daily"
    __table_args__ = (
        UniqueConstraint("ticker_id", "date", name="uq_ohlcv_daily_ticker_date"),
    )

    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    source: Mapped[str | None] = mapped_column(String(32))

    ticker: Mapped["Ticker"] = relationship(back_populates="daily_bars")


class OHLCVIntraday(Base):
    __tablename__ = "ohlcv_intraday"
    __table_args__ = (
        UniqueConstraint(
            "ticker_id", "ts", "timeframe", name="uq_ohlcv_intraday_ticker_ts_tf"
        ),
    )

    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trade_count: Mapped[int | None] = mapped_column(Integer)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    ticker: Mapped["Ticker"] = relationship(back_populates="intraday_bars")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    universe_filter: Mapped[dict | None] = mapped_column(JSONB)
    logic: Mapped[str] = mapped_column(String(8), default="AND", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    results: Mapped[list["ScannerResult"]] = relationship(back_populates="scan")


class ScannerResult(Base):
    __tablename__ = "scanner_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    condition_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    values_snapshot: Mapped[dict | None] = mapped_column(JSONB)

    scan: Mapped["Scan"] = relationship(back_populates="results")
    ticker: Mapped["Ticker"] = relationship(back_populates="scan_results")


class Fundamental(Base):
    __tablename__ = "fundamentals"
    __table_args__ = (
        UniqueConstraint("ticker_id", "period", name="uq_fundamentals_ticker_period"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    reported_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    ticker: Mapped["Ticker"] = relationship()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)  # UUID stored as string
    ticker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="SET NULL")
    )
    scan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("scans.id", ondelete="SET NULL")
    )
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    ticker: Mapped["Ticker | None"] = relationship()
    events: Mapped[list["AlertEvent"]] = relationship(back_populates="alert")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    bar_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    notified_ws: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    alert: Mapped["Alert"] = relationship(back_populates="events")
