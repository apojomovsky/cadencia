import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.models.people import CreatePersonInput, UpdatePersonInput
from em_journal.services.exceptions import AmbiguousError, NotFoundError
from em_journal.services.people import (
    create_person,
    get_person,
    list_people,
    resolve_person,
    update_person,
)


async def test_create_and_get_person(conn: AsyncConnection) -> None:
    created = await create_person(conn, CreatePersonInput(name="Alice"))
    assert created.name == "Alice"
    assert created.status == "active"

    fetched = await get_person(conn, created.id)
    assert fetched.id == created.id
    assert fetched.name == "Alice"


async def test_list_people_filters_by_status(conn: AsyncConnection) -> None:
    await create_person(conn, CreatePersonInput(name="Active One", status="active"))
    await create_person(conn, CreatePersonInput(name="Leaving One", status="leaving"))

    active = await list_people(conn, status="active")
    names = [p.name for p in active]
    assert "Active One" in names
    assert "Leaving One" not in names

    all_people = await list_people(conn, status="all")
    assert len(all_people) == 2


async def test_get_person_not_found(conn: AsyncConnection) -> None:
    with pytest.raises(NotFoundError):
        await get_person(conn, "nonexistent-id")


async def test_resolve_person_exact(conn: AsyncConnection) -> None:
    await create_person(conn, CreatePersonInput(name="Bob Ferreira"))
    results = await resolve_person(conn, "Bob")
    assert len(results) == 1
    assert results[0].name == "Bob Ferreira"


async def test_resolve_person_ambiguous(conn: AsyncConnection) -> None:
    await create_person(conn, CreatePersonInput(name="Alice Smith"))
    await create_person(conn, CreatePersonInput(name="Alice Jones"))
    with pytest.raises(AmbiguousError) as exc_info:
        await resolve_person(conn, "Alice")
    assert len(exc_info.value.candidates) == 2


async def test_resolve_person_not_found(conn: AsyncConnection) -> None:
    with pytest.raises(NotFoundError):
        await resolve_person(conn, "nobody")


async def test_update_person(conn: AsyncConnection) -> None:
    created = await create_person(conn, CreatePersonInput(name="Carlos", role="Engineer"))
    updated = await update_person(conn, created.id, UpdatePersonInput(seniority="P2"))
    assert updated.seniority == "P2"
    assert updated.role == "Engineer"  # unchanged
