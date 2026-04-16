"""Simple SQL migration runner.

Migration files live in db/init/ as NNN_name.sql. The runner tracks
applied migrations in the _migrations table and applies any that are
missing, in filename order. Idempotent: safe to call on every startup.
"""

import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

# SQL files live alongside this module in the package, so they ship with the
# wheel and are available in both dev and the installed container image.
_SQL_DIR = Path(__file__).parent / "sql"


def _find_migration_dir() -> Path:
    """Return the SQL migrations directory, raising if it is missing."""
    if _SQL_DIR.is_dir():
        return _SQL_DIR
    raise FileNotFoundError(f"Migration SQL directory not found: {_SQL_DIR}")


async def run_migrations(conn: AsyncConnection) -> None:
    """Apply any unapplied SQL migrations in order."""
    # Ensure _migrations table exists before we query it
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id         TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """))

    result = await conn.execute(text("SELECT id FROM _migrations"))
    applied = {row[0] for row in result}

    migrations_dir = _find_migration_dir()
    sql_files = sorted(migrations_dir.glob("*.sql"))

    for sql_file in sql_files:
        migration_id = sql_file.stem
        if migration_id in applied:
            logger.debug("Migration already applied: %s", migration_id)
            continue

        logger.info("Applying migration: %s", migration_id)
        sql = sql_file.read_text(encoding="utf-8")

        # SQLite doesn't support multi-statement executemany; split on semicolons
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for statement in statements:
            await conn.execute(text(statement))

        await conn.execute(
            text("INSERT INTO _migrations (id, applied_at) VALUES (:id, datetime('now'))"),
            {"id": migration_id},
        )
        logger.info("Migration applied: %s", migration_id)

    logger.info("All migrations up to date (%d file(s) checked)", len(sql_files))
