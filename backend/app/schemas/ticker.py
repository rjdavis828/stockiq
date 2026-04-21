from datetime import datetime

from pydantic import BaseModel


class TickerBase(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None
    active: bool = True


class TickerRead(TickerBase):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class TickerListParams(BaseModel):
    exchange: str | None = None
    sector: str | None = None
    min_market_cap: int | None = None
    active_only: bool = True
    limit: int = 100
    offset: int = 0
