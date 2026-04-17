import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.stakeholders import CreateStakeholderInput, UpdateStakeholderInput
from cadencia.services.exceptions import NotFoundError
from cadencia.services.stakeholders import (
    create_stakeholder,
    find_stakeholder_by_name_or_alias,
    get_stakeholder,
    update_stakeholder,
)


async def test_update_stakeholder_partial(conn: AsyncConnection) -> None:
    s = await create_stakeholder(conn, CreateStakeholderInput(name="Alice", type="client", organization="Acme"))

    updated = await update_stakeholder(
        conn, s.id, UpdateStakeholderInput(name="Alice Smith", notes="Lead contact")
    )

    assert updated.id == s.id
    assert updated.name == "Alice Smith"
    assert updated.type == "client"
    assert updated.organization == "Acme"
    assert updated.notes == "Lead contact"


async def test_update_stakeholder_not_found(conn: AsyncConnection) -> None:
    with pytest.raises(NotFoundError):
        await update_stakeholder(
            conn, "nonexistent-id", UpdateStakeholderInput(name="Ghost")
        )


async def test_update_stakeholder_type(conn: AsyncConnection) -> None:
    s = await create_stakeholder(conn, CreateStakeholderInput(name="Bob", type="other"))

    updated = await update_stakeholder(conn, s.id, UpdateStakeholderInput(type="am"))

    assert updated.type == "am"
    assert updated.name == "Bob"


async def test_create_stakeholder_with_aliases(conn: AsyncConnection) -> None:
    s = await create_stakeholder(
        conn, CreateStakeholderInput(name="Agustin Alba Chicar", aliases=["Agus"])
    )
    assert s.aliases == ["Agus"]


async def test_update_stakeholder_aliases(conn: AsyncConnection) -> None:
    s = await create_stakeholder(conn, CreateStakeholderInput(name="Gonzalo De Pedro"))
    updated = await update_stakeholder(
        conn, s.id, UpdateStakeholderInput(aliases=["Gonzo"])
    )
    assert updated.aliases == ["Gonzo"]


async def test_clear_stakeholder_aliases(conn: AsyncConnection) -> None:
    s = await create_stakeholder(
        conn, CreateStakeholderInput(name="Someone", aliases=["S"])
    )
    updated = await update_stakeholder(conn, s.id, UpdateStakeholderInput(aliases=[]))
    assert updated.aliases == []


async def test_update_aliases_does_not_touch_when_none(conn: AsyncConnection) -> None:
    s = await create_stakeholder(
        conn, CreateStakeholderInput(name="Persist", aliases=["P"])
    )
    updated = await update_stakeholder(conn, s.id, UpdateStakeholderInput(name="Persist 2"))
    assert updated.aliases == ["P"]


async def test_find_by_name(conn: AsyncConnection) -> None:
    await create_stakeholder(conn, CreateStakeholderInput(name="Gonzalo De Pedro"))
    results = await find_stakeholder_by_name_or_alias(conn, "Gonzalo De Pedro")
    assert len(results) == 1
    assert results[0].name == "Gonzalo De Pedro"


async def test_find_by_alias(conn: AsyncConnection) -> None:
    await create_stakeholder(
        conn, CreateStakeholderInput(name="Gonzalo De Pedro", aliases=["Gonzo"])
    )
    results = await find_stakeholder_by_name_or_alias(conn, "Gonzo")
    assert len(results) == 1
    assert results[0].name == "Gonzalo De Pedro"


async def test_find_case_insensitive(conn: AsyncConnection) -> None:
    await create_stakeholder(
        conn, CreateStakeholderInput(name="Gonzalo De Pedro", aliases=["Gonzo"])
    )
    assert len(await find_stakeholder_by_name_or_alias(conn, "gonzo")) == 1
    assert len(await find_stakeholder_by_name_or_alias(conn, "GONZALO DE PEDRO")) == 1


async def test_find_no_match(conn: AsyncConnection) -> None:
    await create_stakeholder(conn, CreateStakeholderInput(name="Someone"))
    results = await find_stakeholder_by_name_or_alias(conn, "Nobody")
    assert results == []
