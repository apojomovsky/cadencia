"""Composite response models for multi-table derived queries."""

from datetime import date

from pydantic import BaseModel

from em_journal.models.action_items import ActionItem
from em_journal.models.allocations import Allocation
from em_journal.models.observations import Observation
from em_journal.models.one_on_ones import OneOnOne


class StaleAllocation(BaseModel):
    person_id: str
    person_name: str
    days_since_confirmed: int
    current_allocation_type: str | None


class OverdueOneOnOne(BaseModel):
    person_id: str
    person_name: str
    days_since_last_one_on_one: int | None
    next_scheduled: date | None


class OverdueActionItem(BaseModel):
    action_item_id: str
    person_name: str
    text: str
    due_date: date
    days_overdue: int


class StalenessReport(BaseModel):
    stale_allocations: list[StaleAllocation]
    overdue_one_on_ones: list[OverdueOneOnOne]
    overdue_action_items: list[OverdueActionItem]


class OneOnOnePrep(BaseModel):
    """Pre-meeting brief for a single 1:1."""

    person_id: str
    person_name: str
    last_one_on_one: OneOnOne | None
    open_action_items: list[ActionItem]
    recent_observations: list[Observation]  # last 90 days


class PersonOverview(BaseModel):
    """Full person view: the five sections from the web UI spec."""

    person_id: str
    name: str
    role: str | None
    seniority: str | None
    start_date: date | None
    status: str
    current_allocation: Allocation | None
    open_action_items: list[ActionItem]
    next_one_on_one: OneOnOne | None
    last_one_on_one_date: date | None
    recent_observations: list[Observation]  # last 90 days, normal sensitivity only
