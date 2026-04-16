from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Observation(BaseModel):
    id: str
    person_id: str
    observed_at: datetime
    created_at: datetime
    text: str
    tags: list[str]
    source: Literal["manual", "one_on_one", "mcp", "imported"]
    sensitivity: Literal["normal", "personal", "confidential"]


class AddObservationInput(BaseModel):
    person_id: str
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    source: Literal["manual", "one_on_one", "mcp", "imported"] = "manual"
    sensitivity: Literal["normal", "personal", "confidential"] = "normal"
    observed_at: datetime | None = None  # defaults to now in service layer
