"""MCP server for EM Journal: 7 tools via HTTP/SSE transport."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from em_journal.config import settings
from em_journal.db.connection import close_engine, get_connection
from em_journal.db.migrations import run_migrations
from em_journal.models.allocations import UpdateAllocationInput
from em_journal.models.observations import AddObservationInput
from em_journal.models.one_on_ones import ActionItemInput, LogOneOnOneInput
from em_journal.services import people as people_svc
from em_journal.services.action_items import complete_action_item as svc_complete
from em_journal.services.allocations import get_current_allocation
from em_journal.services.allocations import update_allocation as svc_update_alloc
from em_journal.services.exceptions import AmbiguousError, NotFoundError
from em_journal.services.observations import add_observation as svc_add_obs
from em_journal.services.one_on_ones import log_one_on_one as svc_log_oo
from em_journal.services.queries import get_person_overview
from em_journal.services.queries import whats_stale as svc_whats_stale

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

mcp = FastMCP("EM Journal")


# ---- Helpers ---------------------------------------------------------------

async def _resolve(conn: Any, person_input: str) -> Any:
    """Resolve a person name or UUID to PersonDetail. Raises NotFoundError or AmbiguousError."""
    try:
        return await people_svc.get_person(conn, person_input, settings.owner_id)
    except NotFoundError:
        pass
    matches = await people_svc.resolve_person(conn, person_input, settings.owner_id)
    return await people_svc.get_person(conn, matches[0].id, settings.owner_id)


def _err(kind: str, message: str, candidates: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"error": kind, "message": message}
    if candidates:
        result["candidates"] = candidates
    return result


# ---- Tools -----------------------------------------------------------------

@mcp.tool()
async def list_people(status: str = "active") -> list[dict[str, Any]]:
    """List all direct reports with summary info.

    Returns each person's name, role, seniority, current allocation type,
    last 1:1 date, and open action item count.

    status: active (default) | leaving | left | all
    """
    async with get_connection() as conn:
        people = await people_svc.list_people(conn, settings.owner_id, status=status)
    return [
        {
            "id": p.id,
            "name": p.name,
            "role": p.role,
            "seniority": p.seniority,
            "current_allocation_type": p.current_allocation_type,
            "last_one_on_one_date": str(p.last_one_on_one_date) if p.last_one_on_one_date else None,
            "open_action_items_count": p.open_action_items_count,
        }
        for p in people
    ]


@mcp.tool()
async def get_person(person: str) -> dict[str, Any]:
    """Get the full current overview for one person.

    Returns current allocation, recent observations (last 90 days),
    open action items, last 1:1 date, and next scheduled 1:1.

    person: name (partial match ok) or UUID.
    Returns an Ambiguous error listing candidates if the name matches multiple people.
    """
    async with get_connection() as conn:
        try:
            detail = await _resolve(conn, person)
        except NotFoundError:
            return _err("NotFound", f"No person found matching {person!r}")
        except AmbiguousError as e:
            return _err("Ambiguous", f"Multiple people match {person!r}", candidates=e.candidates)

        overview = await get_person_overview(conn, detail.id, settings.owner_id)

    return {
        "person_id": overview.person_id,
        "name": overview.name,
        "role": overview.role,
        "seniority": overview.seniority,
        "start_date": str(overview.start_date) if overview.start_date else None,
        "status": overview.status,
        "current_allocation": (
            overview.current_allocation.model_dump(mode="json")
            if overview.current_allocation else None
        ),
        "open_action_items": [
            ai.model_dump(mode="json") for ai in overview.open_action_items
        ],
        "next_one_on_one": (
            overview.next_one_on_one.model_dump(mode="json")
            if overview.next_one_on_one else None
        ),
        "last_one_on_one_date": (
            str(overview.last_one_on_one_date) if overview.last_one_on_one_date else None
        ),
        "recent_observations": [
            obs.model_dump(mode="json") for obs in overview.recent_observations
        ],
    }


@mcp.tool()
async def add_observation(
    person: str,
    text: str,
    tags: list[str] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Record a new observation about a person. Primary capture tool.

    person: name (partial match ok) or UUID.
    text: the observation in plain text or markdown. Can be brief.
    tags: optional list. Common values: growth, attrition-risk, feedback-given,
          praise, concern, career, allocation, one_on_one.
    observed_at: ISO 8601 date or datetime when this occurred. Defaults to now.
    """
    async with get_connection() as conn:
        try:
            detail = await _resolve(conn, person)
        except NotFoundError:
            return _err("NotFound", f"No person found matching {person!r}")
        except AmbiguousError as e:
            return _err("Ambiguous", f"Multiple people match {person!r}", candidates=e.candidates)

        data = AddObservationInput(
            person_id=detail.id,
            text=text,
            tags=tags or [],
            source="mcp",
            observed_at=observed_at,  # type: ignore[arg-type]
        )
        obs = await svc_add_obs(conn, data, owner_id=settings.owner_id, source="mcp")

    return {
        "id": obs.id,
        "person_id": obs.person_id,
        "person_name": detail.name,
        "observed_at": str(obs.observed_at),
    }


@mcp.tool()
async def log_one_on_one(
    person: str,
    date: str,
    notes: str | None = None,
    action_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Record a completed 1:1 meeting with optional notes and action items.

    person: name (partial match ok) or UUID.
    date: ISO 8601 date of the meeting (e.g. 2026-04-16).
    notes: meeting notes, plain text or markdown.
    action_items: list of objects with keys:
      - text (required): what needs to be done
      - owner: "manager" (default) or "report"
      - due_date: ISO 8601 date, optional
    """
    async with get_connection() as conn:
        try:
            detail = await _resolve(conn, person)
        except NotFoundError:
            return _err("NotFound", f"No person found matching {person!r}")
        except AmbiguousError as e:
            return _err("Ambiguous", f"Multiple people match {person!r}", candidates=e.candidates)

        ai_inputs = [
            ActionItemInput(
                text=item["text"],
                owner_role=item.get("owner", "manager"),
                due_date=item.get("due_date"),
            )
            for item in (action_items or [])
        ]
        data = LogOneOnOneInput(
            person_id=detail.id,
            scheduled_date=date,  # type: ignore[arg-type]
            notes=notes,
            action_items=ai_inputs,
        )
        oo, ai_count = await svc_log_oo(conn, data, owner_id=settings.owner_id, source="mcp")

    return {
        "one_on_one_id": oo.id,
        "person_id": oo.person_id,
        "person_name": detail.name,
        "action_items_created": ai_count,
    }


@mcp.tool()
async def update_allocation(
    person: str,
    type: str,
    client_or_project: str | None = None,
    percent: int | None = None,
    rate_band: str | None = None,
    start_date: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update the current allocation for a person.

    Ends the previous allocation and creates a new one starting today (or start_date).

    person: name (partial match ok) or UUID.
    type: "client" | "internal" | "bench"
    client_or_project: client or project name. Required for client/internal; omit for bench.
    percent: allocation percentage 0-100.
    rate_band: billing rate band, "P1" | "P2" | "P3".
    start_date: ISO 8601 date. Defaults to today.
    notes: reason for the change. Optional but encouraged so future-you remembers why.
    """
    async with get_connection() as conn:
        try:
            detail = await _resolve(conn, person)
        except NotFoundError:
            return _err("NotFound", f"No person found matching {person!r}")
        except AmbiguousError as e:
            return _err("Ambiguous", f"Multiple people match {person!r}", candidates=e.candidates)

        prev = await get_current_allocation(conn, detail.id, settings.owner_id)
        data = UpdateAllocationInput(
            person_id=detail.id,
            type=type,  # type: ignore[arg-type]
            client_or_project=client_or_project,
            percent=percent,
            rate_band=rate_band,  # type: ignore[arg-type]
            start_date=start_date,  # type: ignore[arg-type]
            notes=notes,
        )
        alloc = await svc_update_alloc(conn, data, owner_id=settings.owner_id, source="mcp")

    return {
        "allocation_id": alloc.id,
        "person_id": alloc.person_id,
        "person_name": detail.name,
        "previous_allocation_ended": prev is not None,
    }


@mcp.tool()
async def complete_action_item(
    action_item_id: str,
    completion_notes: str | None = None,
) -> dict[str, Any]:
    """Mark an action item as done.

    action_item_id: UUID of the action item (visible in get_person output).
    completion_notes: optional notes on how it was resolved.
    """
    async with get_connection() as conn:
        try:
            item = await svc_complete(
                conn, action_item_id,
                owner_id=settings.owner_id,
                completion_notes=completion_notes,
                source="mcp",
            )
        except NotFoundError:
            return _err("NotFound", f"Action item not found: {action_item_id!r}")

        person = await people_svc.get_person(conn, item.person_id, settings.owner_id)

    return {
        "action_item_id": item.id,
        "person_name": person.name,
        "text": item.text,
        "completed_at": str(item.completed_at),
    }


@mcp.tool()
async def whats_stale(
    allocation_threshold_days: int = 45,
    one_on_one_threshold_days: int = 14,
) -> dict[str, Any]:
    """Monday-morning check: who needs attention?

    Returns people with stale allocations, overdue 1:1s, and overdue action items.

    allocation_threshold_days: flag allocation as stale if not confirmed in this many days (default 45).
    one_on_one_threshold_days: flag person as overdue if last 1:1 was more than this many days ago (default 14).
    """
    async with get_connection() as conn:
        report = await svc_whats_stale(
            conn,
            owner_id=settings.owner_id,
            allocation_threshold_days=allocation_threshold_days,
            one_on_one_threshold_days=one_on_one_threshold_days,
        )
    return report.model_dump(mode="json")


# ---- ASGI app (SSE transport + health endpoint) ----------------------------

@asynccontextmanager
async def lifespan(app: Starlette):  # type: ignore[type-arg]
    logger.info("EM Journal MCP starting up")
    async with get_connection() as conn:
        await run_migrations(conn)
    yield
    await close_engine()
    logger.info("EM Journal MCP shut down")


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/health", health),
        Mount("/", app=mcp.sse_app()),
    ],
)
