import logging

import uvicorn
from fastapi import FastAPI

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

app = FastAPI(title="EM Journal MCP", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Phase 6: MCP tools and SSE transport will be added here


if __name__ == "__main__":
    logger.info("Starting EM Journal MCP server on port 8081")
    uvicorn.run("em_journal_mcp.server:app", host="0.0.0.0", port=8081)
