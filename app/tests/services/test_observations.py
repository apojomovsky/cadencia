from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.models.observations import AddObservationInput
from em_journal.models.people import CreatePersonInput
from em_journal.services.observations import add_observation, list_observations
from em_journal.services.people import create_person


async def test_add_and_list_observation(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Diana"))
    obs = await add_observation(
        conn,
        AddObservationInput(
            person_id=person.id,
            text="Great in the planning session.",
            tags=["growth"],
        ),
    )
    assert obs.person_id == person.id
    assert obs.text == "Great in the planning session."
    assert "growth" in obs.tags
    assert obs.sensitivity == "normal"


async def test_list_observations_excludes_sensitive_by_default(
    conn: AsyncConnection,
) -> None:
    person = await create_person(conn, CreatePersonInput(name="Eve"))
    await add_observation(
        conn,
        AddObservationInput(person_id=person.id, text="Normal note."),
    )
    await add_observation(
        conn,
        AddObservationInput(
            person_id=person.id, text="Personal note.", sensitivity="personal"
        ),
    )

    normal = await list_observations(conn, person.id)
    assert len(normal) == 1
    assert normal[0].sensitivity == "normal"

    all_obs = await list_observations(conn, person.id, include_sensitive=True)
    assert len(all_obs) == 2


async def test_list_observations_filters_by_tag(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Frank"))
    await add_observation(
        conn, AddObservationInput(person_id=person.id, text="A", tags=["growth"])
    )
    await add_observation(
        conn, AddObservationInput(person_id=person.id, text="B", tags=["concern"])
    )

    growth_obs = await list_observations(conn, person.id, tags=["growth"])
    assert len(growth_obs) == 1
    assert growth_obs[0].text == "A"
