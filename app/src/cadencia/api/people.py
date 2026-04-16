from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.api.deps import get_db, get_owner_id
from cadencia.models.people import CreatePersonInput, PersonDetail, PersonSummary, UpdatePersonInput
from cadencia.services import people as svc
from cadencia.services.exceptions import NotFoundError

router = APIRouter(prefix="/people", tags=["people"])


@router.get("", response_model=list[PersonSummary])
async def list_people(
    status: str = "active",
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> list[PersonSummary]:
    return await svc.list_people(conn, owner_id=owner_id, status=status)


@router.post("", response_model=PersonDetail, status_code=201)
async def create_person(
    data: CreatePersonInput,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> PersonDetail:
    return await svc.create_person(conn, data, owner_id=owner_id, source="api")


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> PersonDetail:
    try:
        return await svc.get_person(conn, person_id, owner_id=owner_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{person_id}", response_model=PersonDetail)
async def update_person(
    person_id: str,
    data: UpdatePersonInput,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> PersonDetail:
    try:
        return await svc.update_person(conn, person_id, data, owner_id=owner_id, source="api")
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
