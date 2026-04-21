from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any, Literal
from enum import Enum


class UniverseFilter(BaseModel):
    min_market_cap: Optional[int] = None
    max_market_cap: Optional[int] = None
    exchanges: Optional[List[str]] = None
    sectors: Optional[List[str]] = None
    industries: Optional[List[str]] = None


class IndicatorRef(BaseModel):
    indicator: str
    period: int
    multiplier: Optional[float] = 1.0


FUNDAMENTAL_FIELDS = {"eps", "pe_ratio", "revenue", "market_cap"}

class FieldRef(BaseModel):
    field: Literal["volume"]


class ComparisonValue(BaseModel):
    value: Union[float, int, List[float], List[int]]


class IndicatorComparison(BaseModel):
    indicator: str
    period: int
    multiplier: Optional[float] = 1.0


class Condition(BaseModel):
    indicator: Optional[str] = None
    # field can be "volume" (technical) or a fundamental field (eps/pe_ratio/revenue/market_cap)
    field: Optional[str] = None
    period: Optional[int] = None
    operator: str
    compare_to: Optional[Union[IndicatorComparison, ComparisonValue, FieldRef]] = None
    value: Optional[Union[float, int, List[float], List[int]]] = None

    class Config:
        extra = "forbid"


class ScannerSchema(BaseModel):
    name: str
    description: Optional[str] = None
    universe: UniverseFilter = Field(default_factory=UniverseFilter)
    conditions: List[Condition]
    logic: Literal["AND", "OR"] = "AND"
    active: bool = True


class ScannerCreateRequest(ScannerSchema):
    pass


class ScannerUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    universe: Optional[UniverseFilter] = None
    conditions: Optional[List[Condition]] = None
    logic: Optional[Literal["AND", "OR"]] = None
    active: Optional[bool] = None


class ScannerResultItem(BaseModel):
    ticker_id: int
    symbol: str
    triggered_at: str
    condition_snapshot: dict
    values_snapshot: dict


class ScannerRunResponse(BaseModel):
    scan_id: int
    run_at: str
    results: List[ScannerResultItem]
    total_matched: int


class ScannerResponse(ScannerSchema):
    id: int
    user_id: int
    created_at: str
    updated_at: str
    last_run: Optional[str] = None
    last_run_count: Optional[int] = None
