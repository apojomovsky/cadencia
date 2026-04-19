import json
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.config import settings
from cadencia.models.people import (
    CreatePersonInput,
    PersonDetail,
    PersonSummary,
    UpdatePersonInput,
)
from cadencia.services.exceptions import AmbiguousError, NotFoundError
from cadencia.services.scheduling import next_expected_one_on_one

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
        one_on_one_cadence_days=r.get("one_on_one_cadence_days"),
        recurrence_weekday=r.get("recurrence_weekday"),
        recurrence_week_of_month=r.get("recurrence_week_of_month"),
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
                "SELECT type, client_or_project, last_confirmed_date, percent"
                " FROM allocations WHERE person_id = :pid AND end_date IS NULL"
                " LIMIT 1"
            ),
            {"pid": person_id},
        )
        alloc_row = alloc_result.fetchone()
        alloc_type = None
        alloc_percent = None
        alloc_confirmed = None
        alloc_label = None
        if alloc_row:
            ar = dict(alloc_row._mapping)
            alloc_type = ar["type"]
            alloc_percent = ar.get("percent")
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

        act_result = await conn.execute(
            text(
                "SELECT role FROM activities"
                " WHERE person_id = :pid AND owner_id = :owner AND ended_on IS NULL"
                " ORDER BY started_on ASC"
            ),
            {"pid": person_id, "owner": owner_id},
        )
        active_roles = [row[0] for row in act_result.fetchall()]

        cadence = r.get("one_on_one_cadence_days") or settings.one_on_one_stale_days
        last_oo_date_obj = date.fromisoformat(str(oo_row[0])) if oo_row and oo_row[0] else None
        if last_oo_date_obj and not (next_oo_row and next_oo_row[0]):
            next_expected = next_expected_one_on_one(
                last_oo_date_obj,
                cadence,
                weekday=r.get("recurrence_weekday"),
                week_of_month=r.get("recurrence_week_of_month"),
            )
        elif next_oo_row and next_oo_row[0]:
            next_expected = date.fromisoformat(str(next_oo_row[0]))
        else:
            next_expected = None

        summaries.append(
            PersonSummary(
                id=person_id,
                name=r["name"],
                role=r["role"],
                seniority=r["seniority"],
                status=r["status"],
                current_allocation_type=alloc_type,
                current_allocation_percent=alloc_percent,
                current_allocation_confirmed_date=alloc_confirmed,
                current_allocation_label=alloc_label,
                last_one_on_one_date=oo_row[0] if oo_row else None,
                next_one_on_one_date=next_oo_row[0] if next_oo_row else None,
                open_action_items_count=ai_count,
                one_on_one_cadence_days=r.get("one_on_one_cadence_days"),
                recurrence_weekday=r.get("recurrence_weekday"),
                recurrence_week_of_month=r.get("recurrence_week_of_month"),
                next_expected_date=next_expected,
                active_activity_roles=active_roles,
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
            current_allocation_percent=None,
            current_allocation_confirmed_date=None,
            current_allocation_label=None,
            last_one_on_one_date=None,
            next_one_on_one_date=None,
            open_action_items_count=0,
            one_on_one_cadence_days=r.get("one_on_one_cadence_days"),
            recurrence_weekday=r.get("recurrence_weekday"),
            recurrence_week_of_month=r.get("recurrence_week_of_month"),
            next_expected_date=None,
            active_activity_roles=[],
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
            " status, one_on_one_cadence_days, recurrence_weekday, recurrence_week_of_month,"
            " created_at, updated_at)"
            " VALUES (:id, :owner, :name, :role, :seniority, :start_date,"
            " :status, :cadence, :recurrence_weekday, :recurrence_week_of_month, :now, :now)"
        ),
        {
            "id": person_id,
            "owner": owner_id,
            "name": data.name,
            "role": data.role,
            "seniority": data.seniority,
            "start_date": data.start_date.isoformat() if data.start_date else None,
            "status": data.status,
            "cadence": data.one_on_one_cadence_days,
            "recurrence_weekday": data.recurrence_weekday,
            "recurrence_week_of_month": data.recurrence_week_of_month,
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
    if data.recurrence_weekday is not None:
        updates["recurrence_weekday"] = data.recurrence_weekday
        set_clauses.append("recurrence_weekday = :recurrence_weekday")
    if data.recurrence_week_of_month is not None:
        updates["recurrence_week_of_month"] = data.recurrence_week_of_month
        set_clauses.append("recurrence_week_of_month = :recurrence_week_of_month")

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


async def update_person_full(
    conn: AsyncConnection,
    person_id: str,
    name: str,
    role: str | None,
    seniority: str | None,
    start_date: date | None,
    status: str,
    recurrence_weekday: int | None,
    recurrence_week_of_month: int | None,
    owner_id: str = "default",
    source: str = "api",
) -> PersonDetail:
    """Full-replace update: every field is written, None clears the column."""
    await get_person(conn, person_id, owner_id)
    now = datetime.now(UTC).isoformat()
    await conn.execute(
        text(
            "UPDATE people SET"
            " name = :name, role = :role, seniority = :seniority,"
            " start_date = :start_date, status = :status,"
            " recurrence_weekday = :recurrence_weekday,"
            " recurrence_week_of_month = :recurrence_week_of_month,"
            " updated_at = :now"
            " WHERE id = :id AND owner_id = :owner"
        ),
        {
            "name": name,
            "role": role,
            "seniority": seniority,
            "start_date": start_date.isoformat() if start_date else None,
            "status": status,
            "recurrence_weekday": recurrence_weekday,
            "recurrence_week_of_month": recurrence_week_of_month,
            "now": now,
            "id": person_id,
            "owner": owner_id,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "people",
                "operation": "update_full",
                "record_id": person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_person(conn, person_id, owner_id)


async def set_one_on_one_cadence(
    conn: AsyncConnection,
    person_id: str,
    cadence_days: int | None,
    owner_id: str = "default",
    source: str = "api",
) -> PersonDetail:
    """Set (or clear) the per-person 1:1 cadence override.

    Pass cadence_days=None to remove the override and fall back to the global default.
    """
    await get_person(conn, person_id, owner_id)  # verify exists
    now = datetime.now(UTC).isoformat()
    await conn.execute(
        text(
            "UPDATE people SET one_on_one_cadence_days = :cadence, updated_at = :now"
            " WHERE id = :id AND owner_id = :owner"
        ),
        {"cadence": cadence_days, "now": now, "id": person_id, "owner": owner_id},
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "people",
                "operation": "set_cadence",
                "record_id": person_id,
                "cadence_days": cadence_days,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_person(conn, person_id, owner_id)
