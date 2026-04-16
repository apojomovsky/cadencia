from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.api.deps import get_db, get_owner_id
from cadencia.models.allocations import Allocation, UpdateAllocationInput
from cadencia.services import allocations as svc
from cadencia.services.exceptions import NotFoundError

router = APIRouter(prefix="/allocations", tags=["allocations"])


@router.post("", response_model=Allocation, status_code=201)
async def update_allocation(
    data: UpdateAllocationInput,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> Allocation:
    try:
        return await svc.update_allocation(conn, data, owner_id=owner_id, source="api")
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{person_id}/confirm", response_model=Allocation)
async def confirm_allocation(
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> Allocation:
    try:
        return await svc.confirm_allocation(conn, person_id, owner_id=owner_id, source="api")
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
