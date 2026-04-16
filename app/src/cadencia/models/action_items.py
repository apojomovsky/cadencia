from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    id: str
    person_id: str
    source_one_on_one_id: str | None
    text: str
    owner_role: Literal["manager", "report"]
    due_date: date | None
    status: Literal["open", "done", "dropped"]
    created_at: datetime
    completed_at: datetime | None


class CreateActionItemInput(BaseModel):
    person_id: str
    text: str = Field(min_length=1)
    owner_role: Literal["manager", "report"] = "manager"
    due_date: date | None = None
    source_one_on_one_id: str | None = None
