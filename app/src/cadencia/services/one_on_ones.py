import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.action_items import CreateActionItemInput
from cadencia.models.one_on_ones import LogOneOnOneInput, OneOnOne, OneOnOnePreview
from cadencia.services.action_items import create_action_item
from cadencia.services.people import get_person

logger = logging.getLogger(__name__)


def _row_to_one_on_one(row: object) -> OneOnOne:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return OneOnOne(
        id=r["id"],
        person_id=r["person_id"],
        scheduled_date=r["scheduled_date"],
        completed=bool(r["completed"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def log_one_on_one(
    conn: AsyncConnection,
    data: LogOneOnOneInput,
    owner_id: str = "default",
    source: str = "api",
) -> tuple[OneOnOne, int]:
    """Create a completed 1:1 record with optional action items.

    Returns (one_on_one, action_items_created_count).
    """
    await get_person(conn, data.person_id, owner_id)

    now = datetime.now(UTC).isoformat()
    oo_id = str(uuid.uuid4())

    await conn.execute(
        text(
            "INSERT INTO one_on_ones"
            " (id, owner_id, person_id, scheduled_date, completed, notes,"
            "  created_at, updated_at)"
            " VALUES (:id, :owner, :person_id, :date, 1, :notes, :now, :now)"
        ),
        {
            "id": oo_id,
            "owner": owner_id,
            "person_id": data.person_id,
            "date": data.scheduled_date.isoformat(),
            "notes": data.notes,
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "one_on_ones",
                "operation": "insert",
                "record_id": oo_id,
                "person_id": data.person_id,
                "source": source,
                "ts": now,
            }
        )
    )

    ai_count = 0
    for item in data.action_items:
        await create_action_item(
            conn,
            CreateActionItemInput(
                person_id=data.person_id,
                text=item.text,
                owner_role=item.owner_role,
                due_date=item.due_date,
                source_one_on_one_id=oo_id,
            ),
            owner_id=owner_id,
            source=source,
        )
        ai_count += 1

    result = await conn.execute(
        text("SELECT * FROM one_on_ones WHERE id = :id"), {"id": oo_id}
    )
    return _row_to_one_on_one(result.fetchone()), ai_count


async def get_upcoming_one_on_ones(
    conn: AsyncConnection,
    owner_id: str = "default",
    within_days: int = 7,
) -> list[OneOnOnePreview]:
    result = await conn.execute(
        text(
            "SELECT o.*, p.name AS person_name FROM one_on_ones o"
            " JOIN people p ON o.person_id = p.id"
            " WHERE o.owner_id = :owner AND o.completed = 0"
            "   AND o.scheduled_date <= date('now', :days)"
            "   AND o.scheduled_date >= date('now')"
            " ORDER BY o.scheduled_date ASC"
        ),
        {"owner": owner_id, "days": f"+{within_days} days"},
    )
    rows = result.fetchall()
    return [
        OneOnOnePreview(
            id=dict(r._mapping)["id"],
            person_id=dict(r._mapping)["person_id"],
            person_name=dict(r._mapping)["person_name"],
            scheduled_date=dict(r._mapping)["scheduled_date"],
            completed=bool(dict(r._mapping)["completed"]),
        )
        for r in rows
    ]


async def list_one_on_ones(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
    limit: int = 20,
) -> list[OneOnOne]:
    """Return completed 1:1s for a person, newest first."""
    await get_person(conn, person_id, owner_id)
    result = await conn.execute(
        text(
            "SELECT * FROM one_on_ones"
            " WHERE person_id = :pid AND owner_id = :owner AND completed = 1"
            " ORDER BY scheduled_date DESC"
            " LIMIT :limit"
        ),
        {"pid": person_id, "owner": owner_id, "limit": limit},
    )
    return [_row_to_one_on_one(r) for r in result.fetchall()]


async def get_last_one_on_one(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
) -> OneOnOne | None:
    result = await conn.execute(
        text(
            "SELECT * FROM one_on_ones"
            " WHERE person_id = :pid AND owner_id = :owner AND completed = 1"
            " ORDER BY scheduled_date DESC LIMIT 1"
        ),
        {"pid": person_id, "owner": owner_id},
    )
    row = result.fetchone()
    return _row_to_one_on_one(row) if row else None
