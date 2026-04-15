from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PersonSummary(BaseModel):
    id: str
    name: str
    role: str | None
    seniority: Literal["P1", "P2", "P3"] | None
    status: Literal["active", "leaving", "left"]
    current_allocation_type: Literal["client", "internal", "bench"] | None
    last_one_on_one_date: date | None
    open_action_items_count: int


class PersonDetail(BaseModel):
    id: str
    name: str
    role: str | None
    seniority: Literal["P1", "P2", "P3"] | None
    start_date: date | None
    status: Literal["active", "leaving", "left"]
    created_at: datetime
    updated_at: datetime


class CreatePersonInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = None
    seniority: Literal["P1", "P2", "P3"] | None = None
    start_date: date | None = None
    status: Literal["active", "leaving", "left"] = "active"


class UpdatePersonInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    seniority: Literal["P1", "P2", "P3"] | None = None
    start_date: date | None = None
    status: Literal["active", "leaving", "left"] | None = None
