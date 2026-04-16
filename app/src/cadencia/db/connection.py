"""SQLAlchemy Core engine and session management for SQLite."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from cadencia.config import settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return the shared engine, creating it on first call."""
    global _engine
    if _engine is None:
        db_url = f"sqlite+aiosqlite:///{settings.db_path}"
        _engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        # Enable WAL mode and foreign keys on every new connection
        @event.listens_for(_engine.sync_engine, "connect")
        def on_connect(dbapi_conn: object, _: object) -> None:
            cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


@asynccontextmanager
async def get_connection() -> AsyncGenerator[AsyncConnection, None]:
    """Yield an async connection from the engine."""
    engine = get_engine()
    async with engine.begin() as conn:
        yield conn


async def close_engine() -> None:
    """Dispose the engine. Called on application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")
