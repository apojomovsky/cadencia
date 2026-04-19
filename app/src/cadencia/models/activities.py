from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

ActivityRole = Literal[
    "trainer",
    "tech_mentor",
    "coach",
    "operations_owner",
    "operations_lead",
    "community_rep",
    "team_manager",
    "account_manager",
]

ActivityPower = Literal["P1", "P2", "P3", "P4"]


class Activity(BaseModel):
    id: str
    owner_id: str
    person_id: str
    role: ActivityRole
    power: ActivityPower | None
    started_on: date
    ended_on: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AddActivityInput(BaseModel):
    person_id: str
    role: ActivityRole
    power: ActivityPower | None = None
    started_on: date | None = None
    notes: str | None = None
