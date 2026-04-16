import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.models.people import (
    CreatePersonInput,
    PersonDetail,
    PersonSummary,
    UpdatePersonInput,
)
from em_journal.services.exceptions import AmbiguousError, NotFoundError

logger = logging.getLogger(__name__)


def _row_to_detail(row: object) -> PersonDetail:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return PersonDetail(
        id=r["id"],
        name=r["name"],
        role=r["role"],
        seniority=r["seniority"],
        start_date=r["start_date"],
        status=r["status"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def list_people(
    conn: AsyncConnection,
    owner_id: str = "default",
    status: str = "active",
) -> list[PersonSummary]:
    if status == "all":
        result = await conn.execute(
            text("SELECT * FROM people WHERE owner_id = :owner ORDER BY name"),
            {"owner": owner_id},
        )
    else:
        result = await conn.execute(
            text(
                "SELECT * FROM people WHERE owner_id = :owner AND status = :status"
                " ORDER BY name"
            ),
            {"owner": owner_id, "status": status},
        )
    rows = result.fetchall()

    summaries = []
    for row in rows:
        r = dict(row._mapping)
        person_id = r["id"]

        # Current allocation
        alloc_result = await conn.execute(
            text(
                "SELECT type, client_or_project, last_confirmed_date"
                " FROM allocations WHERE person_id = :pid AND end_date IS NULL"
                " LIMIT 1"
            ),
            {"pid": person_id},
        )
        alloc_row = alloc_result.fetchone()
        alloc_type = None
        alloc_confirmed = None
        alloc_label = None
        if alloc_row:
            ar = dict(alloc_row._mapping)
            alloc_type = ar["type"]
            alloc_confirmed = ar["last_confirmed_date"]
            if ar["client_or_project"]:
                alloc_label = ar["client_or_project"]
            else:
                alloc_label = alloc_type.title() if alloc_type else None

        # Last completed 1:1 date
        oo_result = await conn.execute(
            text(
                "SELECT scheduled_date FROM one_on_ones"
                " WHERE person_id = :pid AND completed = 1"
                " ORDER BY scheduled_date DESC LIMIT 1"
            ),
            {"pid": person_id},
        )
        oo_row = oo_result.fetchone()

        # Next scheduled (uncompleted) 1:1
        next_oo_result = await conn.execute(
            text(
                "SELECT scheduled_date FROM one_on_ones"
                " WHERE person_id = :pid AND completed = 0"
                "   AND scheduled_date >= date('now')"
                " ORDER BY scheduled_date ASC LIMIT 1"
            ),
            {"pid": person_id},
        )
        next_oo_row = next_oo_result.fetchone()

        # Open action items count
        ai_result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM action_items"
                " WHERE person_id = :pid AND status = 'open'"
            ),
            {"pid": person_id},
        )
        ai_count = ai_result.scalar() or 0

        summaries.append(
            PersonSummary(
                id=person_id,
                name=r["name"],
                role=r["role"],
                seniority=r["seniority"],
                status=r["status"],
                current_allocation_type=alloc_type,
                current_allocation_confirmed_date=alloc_confirmed,
                current_allocation_label=alloc_label,
                last_one_on_one_date=oo_row[0] if oo_row else None,
                next_one_on_one_date=next_oo_row[0] if next_oo_row else None,
                open_action_items_count=ai_count,
            )
        )
    return summaries


async def get_person(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
) -> PersonDetail:
    result = await conn.execute(
        text("SELECT * FROM people WHERE id = :id AND owner_id = :owner"),
        {"id": person_id, "owner": owner_id},
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError("person", person_id)
    return _row_to_detail(row)


async def resolve_person(
    conn: AsyncConnection,
    query: str,
    owner_id: str = "default",
) -> list[PersonSummary]:
    """Find people whose name contains the query string (case-insensitive)."""
    result = await conn.execute(
        text(
            "SELECT * FROM people"
            " WHERE owner_id = :owner AND name LIKE :q AND status != 'left'"
            " ORDER BY name"
        ),
        {"owner": owner_id, "q": f"%{query}%"},
    )
    rows = result.fetchall()
    if not rows:
        raise NotFoundError("person", query)
    if len(rows) > 1:
        names = [dict(r._mapping)["name"] for r in rows]
        raise AmbiguousError(query, names)
    # Exactly one match: return as list for consistency
    row = rows[0]
    r = dict(row._mapping)
    return [
        PersonSummary(
            id=r["id"],
            name=r["name"],
            role=r["role"],
            seniority=r["seniority"],
            status=r["status"],
            current_allocation_type=None,
            current_allocation_confirmed_date=None,
            current_allocation_label=None,
            last_one_on_one_date=None,
            next_one_on_one_date=None,
            open_action_items_count=0,
        )
    ]


async def create_person(
    conn: AsyncConnection,
    data: CreatePersonInput,
    owner_id: str = "default",
    source: str = "api",
) -> PersonDetail:
    now = datetime.now(UTC).isoformat()
    person_id = str(uuid.uuid4())
    await conn.execute(
        text(
            "INSERT INTO people (id, owner_id, name, role, seniority, start_date,"
            " status, created_at, updated_at)"
            " VALUES (:id, :owner, :name, :role, :seniority, :start_date,"
            " :status, :now, :now)"
        ),
        {
            "id": person_id,
            "owner": owner_id,
            "name": data.name,
            "role": data.role,
            "seniority": data.seniority,
            "start_date": data.start_date.isoformat() if data.start_date else None,
            "status": data.status,
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "people",
                "operation": "insert",
                "record_id": person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_person(conn, person_id, owner_id)


async def update_person(
    conn: AsyncConnection,
    person_id: str,
    data: UpdatePersonInput,
    owner_id: str = "default",
    source: str = "api",
) -> PersonDetail:
    # Verify exists first
    await get_person(conn, person_id, owner_id)

    now = datetime.now(UTC).isoformat()
    updates: dict[str, object] = {"now": now, "id": person_id, "owner": owner_id}
    set_clauses: list[str] = ["updated_at = :now"]

    if data.name is not None:
        updates["name"] = data.name
        set_clauses.append("name = :name")
    if data.role is not None:
        updates["role"] = data.role
        set_clauses.append("role = :role")
    if data.seniority is not None:
        updates["seniority"] = data.seniority
        set_clauses.append("seniority = :seniority")
    if data.start_date is not None:
        updates["start_date"] = data.start_date.isoformat()
        set_clauses.append("start_date = :start_date")
    if data.status is not None:
        updates["status"] = data.status
        set_clauses.append("status = :status")

    await conn.execute(
        text(
            f"UPDATE people SET {', '.join(set_clauses)}"
            " WHERE id = :id AND owner_id = :owner"
        ),
        updates,
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "people",
                "operation": "update",
                "record_id": person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_person(conn, person_id, owner_id)
