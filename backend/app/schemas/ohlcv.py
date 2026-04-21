from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_serializer


class OHLCVDailyRead(BaseModel):
    ticker_id: int
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap: Decimal | None = None
    adj_close: Decimal | None = None
    source: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer("open", "high", "low", "close", "vwap", "adj_close")
    def serialize_decimal(self, v: Decimal | None) -> float | None:
        return float(v) if v is not None else None


class OHLCVIntradayRead(BaseModel):
    ticker_id: int
    ts: datetime
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    trade_count: int | None = None
    vwap: Decimal | None = None

    model_config = {"from_attributes": True}

    @field_serializer("open", "high", "low", "close", "vwap")
    def serialize_decimal(self, v: Decimal | None) -> float | None:
        return float(v) if v is not None else None


class BackfillRequest(BaseModel):
    symbol: str
    start: date
    end: date
