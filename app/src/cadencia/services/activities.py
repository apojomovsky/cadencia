import json
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.activities import Activity, AddActivityInput
from cadencia.services.exceptions import NotFoundError
from cadencia.services.people import get_person

logger = logging.getLogger(__name__)


def _row_to_activity(row: object) -> Activity:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return Activity(
        id=r["id"],
        owner_id=r["owner_id"],
        person_id=r["person_id"],
        role=r["role"],
        power=r["power"],
        started_on=r["started_on"],
        ended_on=r["ended_on"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def list_active_activities(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
) -> list[Activity]:
    await get_person(conn, person_id, owner_id)

    result = await conn.execute(
        text(
            "SELECT * FROM activities"
            " WHERE person_id = :pid AND owner_id = :owner AND ended_on IS NULL"
            " ORDER BY started_on DESC"
        ),
        {"pid": person_id, "owner": owner_id},
    )
    return [_row_to_activity(row) for row in result.fetchall()]


async def add_activity(
    conn: AsyncConnection,
    data: AddActivityInput,
    owner_id: str = "default",
    source: str = "api",
) -> Activity:
    await get_person(conn, data.person_id, owner_id)

    now = datetime.now(UTC).isoformat()
    started = data.started_on.isoformat() if data.started_on else date.today().isoformat()
    activity_id = str(uuid.uuid4())

    await conn.execute(
        text(
            "INSERT INTO activities"
            " (id, owner_id, person_id, role, power, started_on, ended_on, notes,"
            "  created_at, updated_at)"
            " VALUES (:id, :owner, :person_id, :role, :power, :started_on, NULL, :notes,"
            "  :now, :now)"
        ),
        {
            "id": activity_id,
            "owner": owner_id,
            "person_id": data.person_id,
            "role": data.role,
            "power": data.power,
            "started_on": started,
            "notes": data.notes,
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "activities",
                "operation": "insert",
                "record_id": activity_id,
                "person_id": data.person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM activities WHERE id = :id AND owner_id = :owner"),
        {"id": activity_id, "owner": owner_id},
    )
    return _row_to_activity(result.fetchone())


async def end_activity(
    conn: AsyncConnection,
    activity_id: str,
    owner_id: str = "default",
    source: str = "api",
) -> Activity:
    result = await conn.execute(
        text("SELECT * FROM activities WHERE id = :id AND owner_id = :owner"),
        {"id": activity_id, "owner": owner_id},
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError("activity", activity_id)

    activity = _row_to_activity(row)
    now = datetime.now(UTC).isoformat()
    ended = date.today().isoformat()

    await conn.execute(
        text(
            "UPDATE activities SET ended_on = :ended, updated_at = :now"
            " WHERE id = :id AND owner_id = :owner"
        ),
        {"ended": ended, "now": now, "id": activity.id, "owner": owner_id},
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "activities",
                "operation": "end",
                "record_id": activity.id,
                "person_id": activity.person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM activities WHERE id = :id AND owner_id = :owner"),
        {"id": activity.id, "owner": owner_id},
    )
    return _row_to_activity(result.fetchone())
