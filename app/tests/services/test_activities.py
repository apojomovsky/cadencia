from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.activities import AddActivityInput
from cadencia.models.people import CreatePersonInput
from cadencia.services.activities import add_activity, end_activity, list_active_activities
from cadencia.services.people import create_person


async def test_add_activity(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Alice"))

    activity = await add_activity(
        conn,
        AddActivityInput(person_id=person.id, role="trainer", power="P2"),
    )

    assert activity.person_id == person.id
    assert activity.role == "trainer"
    assert activity.ended_on is None


async def test_end_activity(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Bob"))
    activity = await add_activity(
        conn,
        AddActivityInput(person_id=person.id, role="operations_owner"),
    )

    ended = await end_activity(conn, activity.id)

    assert ended.id == activity.id
    assert ended.ended_on is not None


async def test_list_active_activities(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Carol"))
    first = await add_activity(conn, AddActivityInput(person_id=person.id, role="tech_mentor"))
    second = await add_activity(conn, AddActivityInput(person_id=person.id, role="community_rep"))
    await end_activity(conn, first.id)

    activities = await list_active_activities(conn, person.id)

    assert len(activities) == 1
    assert activities[0].id == second.id
