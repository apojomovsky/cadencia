from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Stakeholder(BaseModel):
    id: str
    name: str
    type: Literal["am", "client", "internal", "other"]
    organization: str | None
    email: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CreateStakeholderInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["am", "client", "internal", "other"] = "other"
    organization: str | None = None
    email: str | None = None
    notes: str | None = None
