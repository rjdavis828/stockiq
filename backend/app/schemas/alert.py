from datetime import datetime

from pydantic import BaseModel


class AlertCreate(BaseModel):
    ticker_id: int | None = None
    scan_id: int | None = None
    condition: dict


class AlertUpdate(BaseModel):
    condition: dict | None = None
    status: str | None = None


class AlertRead(BaseModel):
    id: int
    user_id: str
    ticker_id: int | None = None
    scan_id: int | None = None
    condition: dict
    status: str
    notified_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
