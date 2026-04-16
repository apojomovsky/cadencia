from datetime import date, datetime

from pydantic import BaseModel


class StakeholderFeedback(BaseModel):
    id: str
    person_id: str
    stakeholder_id: str | None
    received_date: date
    content: str
    tags: list[str]
    created_at: datetime


class AddFeedbackInput(BaseModel):
    person_id: str
    stakeholder_id: str | None = None
    received_date: date | None = None
    content: str
    tags: list[str] = []
