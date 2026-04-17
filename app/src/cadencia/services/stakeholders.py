import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.stakeholders import CreateStakeholderInput, Stakeholder
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
            " created_at, updated_at)"
            " VALUES (:id, :owner, :name, :type, :org, :notes, :now, :now)"
        ),
        {
            "id": sid,
            "owner": owner_id,
            "name": data.name,
            "type": data.type,
            "org": data.organization,
            "notes": data.notes,
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
