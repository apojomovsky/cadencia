"""Shared fixtures for service layer tests.

Each test gets a fresh SQLite database with all migrations applied.
No mocking: tests run against a real (temp file) SQLite instance.
"""

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from em_journal.db.migrations import run_migrations


@pytest_asyncio.fixture
async def conn(tmp_path):  # type: ignore[no-untyped-def]
    """Yield a fresh migrated async connection for each test."""
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def on_connect(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as c:
        await run_migrations(c)
        yield c

    await engine.dispose()
