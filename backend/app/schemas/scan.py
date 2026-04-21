from datetime import datetime

from pydantic import BaseModel


class ScanCreate(BaseModel):
    name: str
    conditions: list[dict]
    universe_filter: dict | None = None
    logic: str = "AND"


class ScanUpdate(BaseModel):
    name: str | None = None
    conditions: list[dict] | None = None
    universe_filter: dict | None = None
    logic: str | None = None
    active: bool | None = None


class ScanRead(BaseModel):
    id: int
    name: str
    conditions: list[dict]
    universe_filter: dict | None = None
    logic: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScannerResultRead(BaseModel):
    id: int
    scan_id: int
    ticker_id: int
    triggered_at: datetime
    condition_snapshot: dict | None = None
    values_snapshot: dict | None = None

    model_config = {"from_attributes": True}
