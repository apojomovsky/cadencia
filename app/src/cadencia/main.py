import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from cadencia.config import settings
from cadencia.db.connection import close_engine, get_connection
from cadencia.db.migrations import run_migrations

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Cadencia starting up")
    async with get_connection() as conn:
        await run_migrations(conn)
    yield
    await close_engine()
    logger.info("Cadencia shut down")


app = FastAPI(title="Cadencia", version="0.1.0", lifespan=lifespan)

# Routes
from cadencia.api import (  # noqa: E402
    action_items,
    allocations,
    health,
    observations,
    one_on_ones,
    people,
)
from cadencia.web import router as web_router  # noqa: E402

app.include_router(health.router, prefix="/api")
app.include_router(people.router, prefix="/api")
app.include_router(observations.router, prefix="/api")
app.include_router(one_on_ones.router, prefix="/api")
app.include_router(action_items.router, prefix="/api")
app.include_router(allocations.router, prefix="/api")
app.include_router(web_router.router)

_static_dir = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
