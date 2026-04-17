from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PersonSummary(BaseModel):
    id: str
    name: str
    role: str | None
    seniority: str | None
    status: Literal["active", "leaving", "left"]
    current_allocation_type: Literal["client", "internal", "bench"] | None
    current_allocation_percent: int | None
    current_allocation_confirmed_date: date | None
    current_allocation_label: str | None
    last_one_on_one_date: date | None
    next_one_on_one_date: date | None
    open_action_items_count: int
    one_on_one_cadence_days: int | None
    recurrence_weekday: int | None
    recurrence_week_of_month: int | None
    next_expected_date: date | None


class PersonDetail(BaseModel):
    id: str
    name: str
    role: str | None
    seniority: str | None
    start_date: date | None
    status: Literal["active", "leaving", "left"]
    created_at: datetime
    updated_at: datetime
    one_on_one_cadence_days: int | None
    recurrence_weekday: int | None
    recurrence_week_of_month: int | None


class CreatePersonInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = None
    seniority: str | None = None
    start_date: date | None = None
    status: Literal["active", "leaving", "left"] = "active"
    one_on_one_cadence_days: int | None = None
    recurrence_weekday: int | None = None
    recurrence_week_of_month: int | None = None


class UpdatePersonInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    seniority: str | None = None
    start_date: date | None = None
    status: Literal["active", "leaving", "left"] | None = None
    recurrence_weekday: int | None = None
    recurrence_week_of_month: int | None = None
