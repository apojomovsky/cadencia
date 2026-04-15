from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Allocation(BaseModel):
    id: str
    person_id: str
    type: Literal["client", "internal", "bench"]
    client_or_project: str | None
    percent: int | None
    rate_band: Literal["P1", "P2", "P3"] | None
    start_date: date
    end_date: date | None
    last_confirmed_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime


class UpdateAllocationInput(BaseModel):
    person_id: str
    type: Literal["client", "internal", "bench"]
    client_or_project: str | None = None
    percent: int | None = Field(default=None, ge=0, le=100)
    rate_band: Literal["P1", "P2", "P3"] | None = None
    start_date: date | None = None  # defaults to today in service layer
    notes: str | None = None
