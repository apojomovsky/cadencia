import json
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.allocations import Allocation, UpdateAllocationInput
from cadencia.services.exceptions import NotFoundError
from cadencia.services.people import get_person

logger = logging.getLogger(__name__)


def _row_to_allocation(row: object) -> Allocation:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return Allocation(
        id=r["id"],
        person_id=r["person_id"],
        type=r["type"],
        client_or_project=r["client_or_project"],
        percent=r["percent"],
        rate_band=r["rate_band"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        last_confirmed_date=r["last_confirmed_date"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        focus=r.get("focus"),
        activity_type=r.get("activity_type"),
        stakeholder_id=r.get("stakeholder_id"),
    )


async def get_current_allocation(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
) -> Allocation | None:
    result = await conn.execute(
        text(
            "SELECT * FROM allocations"
            " WHERE person_id = :pid AND owner_id = :owner AND end_date IS NULL"
            " ORDER BY start_date DESC LIMIT 1"
        ),
        {"pid": person_id, "owner": owner_id},
    )
    row = result.fetchone()
    return _row_to_allocation(row) if row else None


async def update_allocation(
    conn: AsyncConnection,
    data: UpdateAllocationInput,
    owner_id: str = "default",
    source: str = "api",
) -> Allocation:
    """End any current allocation and create a new one."""
    await get_person(conn, data.person_id, owner_id)

    now = datetime.now(UTC).isoformat()
    today = date.today().isoformat()
    start = data.start_date.isoformat() if data.start_date else today

    # End the current allocation (if any)
    prev = await get_current_allocation(conn, data.person_id, owner_id)
    ended = False
    if prev is not None:
        await conn.execute(
            text(
                "UPDATE allocations SET end_date = :end, updated_at = :now"
                " WHERE id = :id"
            ),
            {"end": start, "now": now, "id": prev.id},
        )
        ended = True

    alloc_id = str(uuid.uuid4())
    await conn.execute(
        text(
            "INSERT INTO allocations"
            " (id, owner_id, person_id, type, client_or_project, percent, rate_band,"
            "  start_date, end_date, last_confirmed_date, notes, focus, activity_type,"
            "  stakeholder_id, created_at, updated_at)"
            " VALUES (:id, :owner, :person_id, :type, :client, :percent, :rate_band,"
            "  :start, NULL, :today, :notes, :focus, :activity_type,"
            "  :stakeholder_id, :now, :now)"
        ),
        {
            "id": alloc_id,
            "owner": owner_id,
            "person_id": data.person_id,
            "type": data.type,
            "client": data.client_or_project,
            "percent": data.percent,
            "rate_band": data.rate_band,
            "start": start,
            "today": today,
            "notes": data.notes,
            "focus": data.focus,
            "activity_type": data.activity_type,
            "stakeholder_id": data.stakeholder_id,
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "allocations",
                "operation": "insert",
                "record_id": alloc_id,
                "person_id": data.person_id,
                "previous_ended": ended,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM allocations WHERE id = :id"), {"id": alloc_id}
    )
    return _row_to_allocation(result.fetchone())


async def confirm_allocation(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
    source: str = "api",
) -> Allocation:
    """Touch last_confirmed_date on the current allocation without changing anything else."""
    alloc = await get_current_allocation(conn, person_id, owner_id)
    if alloc is None:
        raise NotFoundError("allocation", f"person {person_id}")

    now = datetime.now(UTC).isoformat()
    today = date.today().isoformat()
    await conn.execute(
        text(
            "UPDATE allocations SET last_confirmed_date = :today, updated_at = :now"
            " WHERE id = :id"
        ),
        {"today": today, "now": now, "id": alloc.id},
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "allocations",
                "operation": "confirm",
                "record_id": alloc.id,
                "person_id": person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM allocations WHERE id = :id"), {"id": alloc.id}
    )
    return _row_to_allocation(result.fetchone())
