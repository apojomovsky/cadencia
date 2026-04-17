import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.stakeholders import CreateStakeholderInput, Stakeholder, UpdateStakeholderInput
from cadencia.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def _row_to_stakeholder(row: object) -> Stakeholder:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return Stakeholder(
        id=r["id"],
        name=r["name"],
        type=r["type"],
        organization=r.get("organization"),
        notes=r.get("notes"),
        aliases=json.loads(r.get("aliases") or "[]"),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def list_stakeholders(
    conn: AsyncConnection,
    owner_id: str = "default",
) -> list[Stakeholder]:
    result = await conn.execute(
        text("SELECT * FROM stakeholders WHERE owner_id = :owner ORDER BY name"),
        {"owner": owner_id},
    )
    return [_row_to_stakeholder(r) for r in result.fetchall()]


async def get_stakeholder(
    conn: AsyncConnection,
    stakeholder_id: str,
    owner_id: str = "default",
) -> Stakeholder:
    result = await conn.execute(
        text("SELECT * FROM stakeholders WHERE id = :id AND owner_id = :owner"),
        {"id": stakeholder_id, "owner": owner_id},
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError("stakeholder", stakeholder_id)
    return _row_to_stakeholder(row)


async def find_stakeholder_by_name_or_alias(
    conn: AsyncConnection,
    query: str,
    owner_id: str = "default",
) -> list[Stakeholder]:
    """Return stakeholders whose name or any alias matches query (case-insensitive, exact)."""
    q = query.strip().lower()
    result = await conn.execute(
        text("""
            SELECT DISTINCT s.*
            FROM stakeholders s
            WHERE s.owner_id = :owner
              AND (
                lower(s.name) = :q
                OR EXISTS (
                    SELECT 1 FROM json_each(s.aliases) WHERE lower(value) = :q
                )
              )
            ORDER BY s.name
        """),
        {"owner": owner_id, "q": q},
    )
    return [_row_to_stakeholder(r) for r in result.fetchall()]


async def create_stakeholder(
    conn: AsyncConnection,
    data: CreateStakeholderInput,
    owner_id: str = "default",
    source: str = "api",
) -> Stakeholder:
    now = datetime.now(UTC).isoformat()
    sid = str(uuid.uuid4())
    await conn.execute(
        text(
            "INSERT INTO stakeholders (id, owner_id, name, type, organization, notes,"
            " aliases, created_at, updated_at)"
            " VALUES (:id, :owner, :name, :type, :org, :notes, :aliases, :now, :now)"
        ),
        {
            "id": sid,
            "owner": owner_id,
            "name": data.name,
            "type": data.type,
            "org": data.organization,
            "notes": data.notes,
            "aliases": json.dumps(data.aliases),
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "stakeholders",
                "operation": "insert",
                "record_id": sid,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_stakeholder(conn, sid, owner_id)


async def update_stakeholder(
    conn: AsyncConnection,
    stakeholder_id: str,
    data: UpdateStakeholderInput,
    owner_id: str = "default",
    source: str = "api",
) -> Stakeholder:
    await get_stakeholder(conn, stakeholder_id, owner_id)

    now = datetime.now(UTC).isoformat()
    updates: dict[str, object] = {"now": now, "id": stakeholder_id, "owner": owner_id}
    set_clauses: list[str] = ["updated_at = :now"]

    if data.name is not None:
        updates["name"] = data.name
        set_clauses.append("name = :name")
    if data.type is not None:
        updates["type"] = data.type
        set_clauses.append("type = :type")
    if data.organization is not None:
        updates["organization"] = data.organization
        set_clauses.append("organization = :organization")
    if data.notes is not None:
        updates["notes"] = data.notes
        set_clauses.append("notes = :notes")
    if data.aliases is not None:
        updates["aliases"] = json.dumps(data.aliases)
        set_clauses.append("aliases = :aliases")

    await conn.execute(
        text(
            f"UPDATE stakeholders SET {', '.join(set_clauses)}"
            " WHERE id = :id AND owner_id = :owner"
        ),
        updates,
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "stakeholders",
                "operation": "update",
                "record_id": stakeholder_id,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_stakeholder(conn, stakeholder_id, owner_id)
