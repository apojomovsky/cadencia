from datetime import date, datetime

from pydantic import BaseModel, Field


class ActionItemInput(BaseModel):
    """Inline action item captured during a 1:1 log."""

    text: str = Field(min_length=1)
    owner_role: str = "manager"  # manager | report
    due_date: date | None = None


class OneOnOne(BaseModel):
    id: str
    person_id: str
    scheduled_date: date
    completed: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class LogOneOnOneInput(BaseModel):
    person_id: str
    scheduled_date: date
    notes: str | None = None
    action_items: list[ActionItemInput] = Field(default_factory=list)


class OneOnOnePreview(BaseModel):
    id: str
    person_id: str
    person_name: str
    scheduled_date: date
    completed: bool
