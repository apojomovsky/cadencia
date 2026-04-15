from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.models.allocations import UpdateAllocationInput
from em_journal.models.people import CreatePersonInput
from em_journal.services.allocations import (
    confirm_allocation,
    get_current_allocation,
    update_allocation,
)
from em_journal.services.people import create_person


async def test_update_allocation_creates_new(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Katia"))
    alloc = await update_allocation(
        conn,
        UpdateAllocationInput(
            person_id=person.id,
            type="client",
            client_or_project="AcmeCorp",
            percent=100,
            rate_band="P2",
        ),
    )
    assert alloc.type == "client"
    assert alloc.client_or_project == "AcmeCorp"
    assert alloc.end_date is None


async def test_update_allocation_ends_previous(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Leo"))
    first = await update_allocation(
        conn,
        UpdateAllocationInput(person_id=person.id, type="bench"),
    )
    assert first.end_date is None

    second = await update_allocation(
        conn,
        UpdateAllocationInput(
            person_id=person.id, type="client", client_or_project="BetaCo"
        ),
    )
    # Current allocation should be the new one
    current = await get_current_allocation(conn, person.id)
    assert current is not None
    assert current.id == second.id
    assert current.type == "client"


async def test_confirm_allocation(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Marta"))
    await update_allocation(
        conn, UpdateAllocationInput(person_id=person.id, type="internal",
                                    client_or_project="Arch Initiative")
    )
    confirmed = await confirm_allocation(conn, person.id)
    assert confirmed.type == "internal"
