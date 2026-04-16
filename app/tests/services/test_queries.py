from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.allocations import UpdateAllocationInput
from cadencia.models.observations import AddObservationInput
from cadencia.models.one_on_ones import LogOneOnOneInput
from cadencia.models.people import CreatePersonInput
from cadencia.services.allocations import update_allocation
from cadencia.services.observations import add_observation
from cadencia.services.one_on_ones import log_one_on_one
from cadencia.services.people import create_person
from cadencia.services.queries import (
    get_person_overview,
    prepare_one_on_one,
    whats_stale,
)


async def test_whats_stale_returns_people_without_one_on_ones(
    conn: AsyncConnection,
) -> None:
    person = await create_person(conn, CreatePersonInput(name="Nadia"))
    report = await whats_stale(conn, one_on_one_threshold_days=14)
    person_ids = [o.person_id for o in report.overdue_one_on_ones]
    assert person.id in person_ids


async def test_whats_stale_no_overdue_after_recent_one_on_one(
    conn: AsyncConnection,
) -> None:
    person = await create_person(conn, CreatePersonInput(name="Omar"))
    await log_one_on_one(
        conn,
        LogOneOnOneInput(person_id=person.id, scheduled_date=date.today()),
    )
    report = await whats_stale(conn, one_on_one_threshold_days=14)
    person_ids = [o.person_id for o in report.overdue_one_on_ones]
    assert person.id not in person_ids


async def test_whats_stale_overdue_action_items(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Paula"))
    from cadencia.models.action_items import CreateActionItemInput
    from cadencia.services.action_items import create_action_item

    past_date = date.today() - timedelta(days=5)
    await create_action_item(
        conn,
        CreateActionItemInput(
            person_id=person.id,
            text="Overdue task",
            due_date=past_date,
        ),
    )
    report = await whats_stale(conn)
    assert any(a.person_name == "Paula" for a in report.overdue_action_items)


async def test_prepare_one_on_one(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Quincy"))
    await add_observation(
        conn, AddObservationInput(person_id=person.id, text="Looking good", tags=["growth"])
    )
    prep = await prepare_one_on_one(conn, person.id)
    assert prep.person_name == "Quincy"
    assert len(prep.recent_observations) == 1
    assert prep.last_one_on_one is None


async def test_get_person_overview(conn: AsyncConnection) -> None:
    person = await create_person(
        conn, CreatePersonInput(name="Rosa", role="Tech Lead", seniority="P3")
    )
    await update_allocation(
        conn,
        UpdateAllocationInput(
            person_id=person.id, type="client", client_or_project="DeltaCorp", percent=80
        ),
    )
    overview = await get_person_overview(conn, person.id)
    assert overview.name == "Rosa"
    assert overview.current_allocation is not None
    assert overview.current_allocation.client_or_project == "DeltaCorp"
    assert overview.status == "active"
