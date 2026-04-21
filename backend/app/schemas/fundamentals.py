from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class FundamentalsResponse(BaseModel):
    id: int
    ticker_id: int
    period: str
    revenue: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = None
    market_cap: Optional[int] = None
    reported_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
