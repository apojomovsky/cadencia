import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from em_journal.config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("EM Journal starting up")
    # Phase 1: database init will go here
    yield
    logger.info("EM Journal shutting down")


app = FastAPI(title="EM Journal", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "version": "0.1.0"}
