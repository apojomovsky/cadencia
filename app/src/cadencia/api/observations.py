from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.api.deps import get_db, get_owner_id
from cadencia.models.observations import AddObservationInput, Observation
from cadencia.services import observations as svc
from cadencia.services.exceptions import NotFoundError

router = APIRouter(prefix="/observations", tags=["observations"])


@router.post("", response_model=Observation, status_code=201)
async def add_observation(
    data: AddObservationInput,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> Observation:
    try:
        return await svc.add_observation(conn, data, owner_id=owner_id, source="api")
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/person/{person_id}", response_model=list[Observation])
async def list_observations(
    person_id: str,
    since: str | None = None,
    tags: str | None = None,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> list[Observation]:
    tag_list = tags.split(",") if tags else None
    try:
        return await svc.list_observations(
            conn, person_id, owner_id=owner_id, since=since, tags=tag_list
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
