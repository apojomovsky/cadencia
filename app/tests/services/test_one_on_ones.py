from datetime import date

from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.one_on_ones import ActionItemInput, LogOneOnOneInput
from cadencia.models.people import CreatePersonInput
from cadencia.services.action_items import get_open_action_items
from cadencia.services.one_on_ones import log_one_on_one
from cadencia.services.people import create_person


async def test_log_one_on_one_creates_record(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Isabel"))
    oo, count = await log_one_on_one(
        conn,
        LogOneOnOneInput(
            person_id=person.id,
            scheduled_date=date.today(),
            notes="Good energy. Wants more ownership.",
        ),
    )
    assert oo.person_id == person.id
    assert oo.completed is True
    assert count == 0


async def test_log_one_on_one_creates_action_items(conn: AsyncConnection) -> None:
    person = await create_person(conn, CreatePersonInput(name="Jorge"))
    oo, count = await log_one_on_one(
        conn,
        LogOneOnOneInput(
            person_id=person.id,
            scheduled_date=date.today(),
            notes="Notes.",
            action_items=[
                ActionItemInput(text="Review his PR", owner_role="manager"),
                ActionItemInput(text="Send updated goals", owner_role="report"),
            ],
        ),
    )
    assert count == 2
    open_ais = await get_open_action_items(conn, person_id=person.id)
    assert len(open_ais) == 2
    owners = {ai.owner_role for ai in open_ais}
    assert owners == {"manager", "report"}
