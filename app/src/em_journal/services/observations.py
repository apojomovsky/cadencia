import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.models.observations import AddObservationInput, Observation
from em_journal.services.people import get_person

logger = logging.getLogger(__name__)


def _row_to_observation(row: object) -> Observation:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return Observation(
        id=r["id"],
        person_id=r["person_id"],
        observed_at=r["observed_at"],
        created_at=r["created_at"],
        text=r["text"],
        tags=json.loads(r["tags"]),
        source=r["source"],
        sensitivity=r["sensitivity"],
    )


async def add_observation(
    conn: AsyncConnection,
    data: AddObservationInput,
    owner_id: str = "default",
    source: str = "api",
) -> Observation:
    # Verify person exists
    await get_person(conn, data.person_id, owner_id)

    now = datetime.now(UTC).isoformat()
    obs_id = str(uuid.uuid4())
    observed_at = data.observed_at.isoformat() if data.observed_at else now

    await conn.execute(
        text(
            "INSERT INTO observations"
            " (id, owner_id, person_id, observed_at, created_at, text, tags, source, sensitivity)"
            " VALUES (:id, :owner, :person_id, :observed_at, :now, :text, :tags, :source, :sensitivity)"
        ),
        {
            "id": obs_id,
            "owner": owner_id,
            "person_id": data.person_id,
            "observed_at": observed_at,
            "now": now,
            "text": data.text,
            "tags": json.dumps(data.tags),
            "source": data.source,
            "sensitivity": data.sensitivity,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "observations",
                "operation": "insert",
                "record_id": obs_id,
                "person_id": data.person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM observations WHERE id = :id"), {"id": obs_id}
    )
    return _row_to_observation(result.fetchone())


async def list_observations(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
    since: str | None = None,
    tags: list[str] | None = None,
    include_sensitive: bool = False,
) -> list[Observation]:
    # Verify person exists
    await get_person(conn, person_id, owner_id)

    conditions = ["person_id = :person_id", "owner_id = :owner"]
    params: dict[str, object] = {"person_id": person_id, "owner": owner_id}

    if not include_sensitive:
        conditions.append("sensitivity = 'normal'")

    if since:
        conditions.append("observed_at >= :since")
        params["since"] = since

    where = " AND ".join(conditions)
    result = await conn.execute(
        text(f"SELECT * FROM observations WHERE {where} ORDER BY observed_at DESC"),
        params,
    )
    rows = result.fetchall()

    observations = [_row_to_observation(r) for r in rows]

    # Post-filter by tags (SQLite has no JSON array contains operator)
    if tags:
        observations = [
            o for o in observations if any(t in o.tags for t in tags)
        ]

    return observations
