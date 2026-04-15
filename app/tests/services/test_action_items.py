from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.models.action_items import CreateActionItemInput
from em_journal.models.people import CreatePersonInput
from em_journal.services.action_items import (
    complete_action_item,
    create_action_item,
    get_open_action_items,
)
from em_journal.services.exceptions import NotFoundError
from em_journal.services.people import create_person
import pytest


async def test_create_and_list_action_item(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Grace"))
    ai = await create_action_item(
        conn,
        CreateActionItemInput(person_id=person.id, text="Follow up on proposal"),
    )
    assert ai.status == "open"
    assert ai.text == "Follow up on proposal"

    open_items = await get_open_action_items(conn, person_id=person.id)
    assert len(open_items) == 1
    assert open_items[0].id == ai.id


async def test_complete_action_item(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Hector"))
    ai = await create_action_item(
        conn,
        CreateActionItemInput(person_id=person.id, text="Send tech radar"),
    )
    done = await complete_action_item(conn, ai.id, completion_notes="Sent on Friday")
    assert done.status == "done"
    assert done.completed_at is not None
    assert "Sent on Friday" in done.text

    open_items = await get_open_action_items(conn, person_id=person.id)
    assert len(open_items) == 0


async def test_complete_nonexistent_raises(conn: AsyncConnection) -> None:
    with pytest.raises(NotFoundError):
        await complete_action_item(conn, "bad-id")
