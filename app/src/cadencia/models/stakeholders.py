from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Stakeholder(BaseModel):
    id: str
    name: str
    type: Literal["am", "client", "internal", "other"]
    organization: str | None
    aliases: list[str]
    created_at: datetime
    updated_at: datetime


class CreateStakeholderInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["am", "client", "internal", "other"] = "other"
    organization: str | None = None
    aliases: list[str] = []


class UpdateStakeholderInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: Literal["am", "client", "internal", "other"] | None = None
    organization: str | None = None
    aliases: list[str] | None = None
