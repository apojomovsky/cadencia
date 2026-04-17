import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.stakeholders import CreateStakeholderInput, UpdateStakeholderInput
from cadencia.services.exceptions import NotFoundError
from cadencia.services.stakeholders import create_stakeholder, get_stakeholder, update_stakeholder


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
