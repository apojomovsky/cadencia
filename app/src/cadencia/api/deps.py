"""FastAPI dependency injection helpers."""

import json
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.config import settings
from cadencia.db.connection import get_connection


async def get_db() -> AsyncGenerator[AsyncConnection, None]:
    """Yield a database connection for a request."""
    async with get_connection() as conn:
        yield conn


def get_owner_id() -> str:
    return settings.owner_id


def get_backup_status() -> dict[str, object]:
    """Read the backup sentinel file. Returns a safe default if missing."""
    path = Path(settings.backup_status_path)
    if not path.exists():
        return {"success": None, "ts": None, "file": None}
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except Exception:
        return {"success": False, "ts": None, "file": None, "error": "unreadable"}
