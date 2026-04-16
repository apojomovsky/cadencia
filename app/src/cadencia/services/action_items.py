import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.action_items import ActionItem, CreateActionItemInput
from cadencia.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def _row_to_action_item(row: object) -> ActionItem:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return ActionItem(
        id=r["id"],
        person_id=r["person_id"],
        source_one_on_one_id=r["source_one_on_one_id"],
        text=r["text"],
        owner_role=r["owner_role"],
        due_date=r["due_date"],
        status=r["status"],
        created_at=r["created_at"],
        completed_at=r["completed_at"],
    )


async def create_action_item(
    conn: AsyncConnection,
    data: CreateActionItemInput,
    owner_id: str = "default",
    source: str = "api",
) -> ActionItem:
    now = datetime.now(UTC).isoformat()
    ai_id = str(uuid.uuid4())

    await conn.execute(
        text(
            "INSERT INTO action_items"
            " (id, owner_id, person_id, source_one_on_one_id, text, owner_role,"
            "  due_date, status, created_at)"
            " VALUES (:id, :owner, :person_id, :oo_id, :text, :owner_role,"
            "  :due_date, 'open', :now)"
        ),
        {
            "id": ai_id,
            "owner": owner_id,
            "person_id": data.person_id,
            "oo_id": data.source_one_on_one_id,
            "text": data.text,
            "owner_role": data.owner_role,
            "due_date": data.due_date.isoformat() if data.due_date else None,
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "action_items",
                "operation": "insert",
                "record_id": ai_id,
                "person_id": data.person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM action_items WHERE id = :id"), {"id": ai_id}
    )
    return _row_to_action_item(result.fetchone())


async def get_open_action_items(
    conn: AsyncConnection,
    owner_id: str = "default",
    person_id: str | None = None,
) -> list[ActionItem]:
    if person_id:
        result = await conn.execute(
            text(
                "SELECT * FROM action_items"
                " WHERE owner_id = :owner AND person_id = :pid AND status = 'open'"
                " ORDER BY due_date ASC NULLS LAST, created_at ASC"
            ),
            {"owner": owner_id, "pid": person_id},
        )
    else:
        result = await conn.execute(
            text(
                "SELECT * FROM action_items"
                " WHERE owner_id = :owner AND status = 'open'"
                " ORDER BY due_date ASC NULLS LAST, created_at ASC"
            ),
            {"owner": owner_id},
        )
    return [_row_to_action_item(r) for r in result.fetchall()]


async def complete_action_item(
    conn: AsyncConnection,
    action_item_id: str,
    owner_id: str = "default",
    completion_notes: str | None = None,
    source: str = "api",
) -> ActionItem:
    result = await conn.execute(
        text(
            "SELECT * FROM action_items WHERE id = :id AND owner_id = :owner"
        ),
        {"id": action_item_id, "owner": owner_id},
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError("action_item", action_item_id)

    now = datetime.now(UTC).isoformat()
    notes_text = completion_notes or ""
    new_text = dict(row._mapping)["text"]
    if notes_text:
        new_text = f"{new_text}\n\nCompletion notes: {notes_text}"

    await conn.execute(
        text(
            "UPDATE action_items SET status = 'done', completed_at = :now, text = :text"
            " WHERE id = :id AND owner_id = :owner"
        ),
        {"now": now, "text": new_text, "id": action_item_id, "owner": owner_id},
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "action_items",
                "operation": "update",
                "record_id": action_item_id,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM action_items WHERE id = :id"), {"id": action_item_id}
    )
    return _row_to_action_item(result.fetchone())
