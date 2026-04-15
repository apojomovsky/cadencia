from fastapi import APIRouter, Depends

from em_journal.api.deps import get_backup_status

router = APIRouter()


@router.get("/health")
async def health(
    backup: dict[str, object] = Depends(get_backup_status),
) -> dict[str, object]:
    return {"status": "ok", "version": "0.1.0", "backup": backup}
