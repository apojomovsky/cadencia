from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.api.deps import get_db, get_owner_id
from em_journal.models.action_items import ActionItem
from em_journal.services.exceptions import NotFoundError
from em_journal.services import action_items as svc

router = APIRouter(prefix="/action-items", tags=["action_items"])


@router.get("", response_model=list[ActionItem])
async def get_open_action_items(
    person_id: str | None = None,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> list[ActionItem]:
    return await svc.get_open_action_items(conn, owner_id=owner_id, person_id=person_id)


@router.post("/{action_item_id}/complete", response_model=ActionItem)
async def complete_action_item(
    action_item_id: str,
    completion_notes: str | None = None,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> ActionItem:
    try:
        return await svc.complete_action_item(
            conn, action_item_id, owner_id=owner_id,
            completion_notes=completion_notes, source="api"
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
