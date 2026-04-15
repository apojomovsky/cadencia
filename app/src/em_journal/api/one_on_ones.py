from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from em_journal.api.deps import get_db, get_owner_id
from em_journal.models.one_on_ones import LogOneOnOneInput, OneOnOne
from em_journal.services.exceptions import NotFoundError
from em_journal.services import one_on_ones as svc

router = APIRouter(prefix="/one-on-ones", tags=["one_on_ones"])


class LogOneOnOneResponse(OneOnOne):
    action_items_created: int


@router.post("", response_model=LogOneOnOneResponse, status_code=201)
async def log_one_on_one(
    data: LogOneOnOneInput,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> LogOneOnOneResponse:
    try:
        oo, count = await svc.log_one_on_one(conn, data, owner_id=owner_id, source="api")
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return LogOneOnOneResponse(action_items_created=count, **oo.model_dump())


@router.get("/upcoming", response_model=list)
async def get_upcoming(
    within_days: int = 7,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> list:
    return await svc.get_upcoming_one_on_ones(conn, owner_id=owner_id, within_days=within_days)
