"""API-level test fixtures using httpx AsyncClient with a temp DB."""

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from em_journal.db.migrations import run_migrations
from em_journal.main import app
import em_journal.db.connection as db_module


@pytest_asyncio.fixture
async def client(tmp_path):  # type: ignore[no-untyped-def]
    """Yield an async TestClient wired to a fresh temp database."""
    db_path = tmp_path / "test_api.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def on_connect(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Run migrations on the temp DB
    async with engine.begin() as conn:
        await run_migrations(conn)

    # Swap the global engine for this test
    original_engine = db_module._engine
    db_module._engine = engine

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    # Restore global engine and dispose temp one
    db_module._engine = original_engine
    await engine.dispose()
