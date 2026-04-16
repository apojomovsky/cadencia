import json
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.feedback import AddFeedbackInput, StakeholderFeedback

logger = logging.getLogger(__name__)


def _row_to_feedback(row: object) -> StakeholderFeedback:
    r = dict(row._mapping)  # type: ignore[union-attr]
    raw_tags = r.get("tags", "[]")
    tags = json.loads(raw_tags) if isinstance(raw_tags, str) else raw_tags
    return StakeholderFeedback(
        id=r["id"],
        person_id=r["person_id"],
        stakeholder_id=r.get("stakeholder_id"),
        received_date=r["received_date"],
        content=r["content"],
        tags=tags,
        created_at=r["created_at"],
    )


async def add_feedback(
    conn: AsyncConnection,
    data: AddFeedbackInput,
    owner_id: str = "default",
    source: str = "api",
) -> StakeholderFeedback:
    now = datetime.now(UTC).isoformat()
    fid = str(uuid.uuid4())
    received = (data.received_date or date.today()).isoformat()
    await conn.execute(
        text(
            "INSERT INTO stakeholder_feedback"
            " (id, owner_id, person_id, stakeholder_id, received_date, content, tags, created_at)"
            " VALUES (:id, :owner, :person_id, :stakeholder_id, :received, :content, :tags, :now)"
        ),
        {
            "id": fid,
            "owner": owner_id,
            "person_id": data.person_id,
            "stakeholder_id": data.stakeholder_id,
            "received": received,
            "content": data.content,
            "tags": json.dumps(data.tags),
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "stakeholder_feedback",
                "operation": "insert",
                "record_id": fid,
                "person_id": data.person_id,
                "source": source,
                "ts": now,
            }
        )
    )
    result = await conn.execute(
        text("SELECT * FROM stakeholder_feedback WHERE id = :id"), {"id": fid}
    )
    return _row_to_feedback(result.fetchone())


async def list_feedback_for_person(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
    limit: int = 10,
) -> list[StakeholderFeedback]:
    result = await conn.execute(
        text(
            "SELECT * FROM stakeholder_feedback"
            " WHERE person_id = :pid AND owner_id = :owner"
            " ORDER BY received_date DESC LIMIT :limit"
        ),
        {"pid": person_id, "owner": owner_id, "limit": limit},
    )
    return [_row_to_feedback(r) for r in result.fetchall()]
