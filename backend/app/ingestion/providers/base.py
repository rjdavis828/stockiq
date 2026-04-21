from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass
class OHLCVBar:
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    adj_close: float | None = None
    source: str = ""


@dataclass
class TickerInfo:
    symbol: str
    name: str
    exchange: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: int | None = None
    active: bool = True
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FundamentalsData:
    symbol: str
    period: str          # e.g. "2024-Q3"
    revenue: Decimal | None = None
    eps: Decimal | None = None
    pe_ratio: Decimal | None = None
    market_cap: int | None = None
    reported_at: datetime | None = None


class BaseProvider(ABC):
    @abstractmethod
    async def fetch_daily(
        self, symbol: str, start: date, end: date
    ) -> list[OHLCVBar]: ...

    @abstractmethod
    async def fetch_tickers(self) -> list[TickerInfo]: ...

    async def fetch_fundamentals(self, symbol: str) -> list[FundamentalsData]:
        return []
