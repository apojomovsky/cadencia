"""Web UI routes: server-rendered HTML via Jinja2 + HTMX."""

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.api.deps import get_backup_status, get_db, get_owner_id
from cadencia.config import settings
from cadencia.services.action_items import complete_action_item
from cadencia.services.exceptions import NotFoundError
from cadencia.services.people import list_people
from cadencia.services.queries import get_person_overview, whats_stale

router = APIRouter(include_in_schema=False)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _backup_context() -> dict[str, object]:
    """Derive template variables from the backup sentinel file."""
    status = get_backup_status()
    ts_raw = status.get("ts")
    overdue = False
    ts_display = None

    if ts_raw:
        try:
            backed_up_at = datetime.fromisoformat(str(ts_raw))
            if backed_up_at.tzinfo is None:
                backed_up_at = backed_up_at.replace(tzinfo=UTC)
            now = datetime.now(UTC)
            delta = now - backed_up_at
            hours = int(delta.total_seconds() // 3600)
            if hours < 1:
                minutes = int(delta.total_seconds() // 60)
                ts_display = f"{minutes}m ago"
            elif hours < 24:
                ts_display = f"{hours}h ago"
            else:
                days = hours // 24
                ts_display = f"{days}d ago"
            overdue = delta.total_seconds() > 25 * 3600
        except Exception:
            ts_display = str(ts_raw)
    else:
        overdue = False

    return {"backup_ts": ts_display, "backup_overdue": overdue}


def _one_on_one_context(
    last_date: date | str | None,
    next_date: date | str | None,
    threshold_days: int,
) -> dict[str, object]:
    today = date.today()
    ctx: dict[str, object] = {
        "one_on_one_days_ago": None,
        "one_on_one_overdue": False,
        "one_on_one_days_until": None,
    }
    if last_date:
        ld = date.fromisoformat(str(last_date)) if isinstance(last_date, str) else last_date
        days_ago = (today - ld).days
        ctx["one_on_one_days_ago"] = days_ago
        ctx["one_on_one_overdue"] = days_ago > threshold_days
    if next_date:
        nd = date.fromisoformat(str(next_date)) if isinstance(next_date, str) else next_date
        days_until = (nd - today).days
        ctx["one_on_one_days_until"] = max(days_until, 0)
    return ctx


def _alloc_context(last_confirmed: date | None, threshold_days: int) -> dict[str, object]:
    if last_confirmed is None:
        return {"alloc_stale_days": 9999}
    days = (date.today() - last_confirmed).days
    if days > threshold_days:
        return {"alloc_stale_days": days}
    return {"alloc_stale_days": None}


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    report = await whats_stale(
        conn,
        owner_id=owner_id,
        allocation_threshold_days=settings.allocation_stale_days,
        one_on_one_threshold_days=settings.one_on_one_stale_days,
    )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "stale_allocs": report.stale_allocations,
            "overdue_oos": report.overdue_one_on_ones,
            "overdue_ais": report.overdue_action_items,
            **_backup_context(),
        },
    )


@router.get("/people", response_class=HTMLResponse)
async def people_list(
    request: Request,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    people = await list_people(conn, owner_id)
    date.today()
    threshold_oo = settings.one_on_one_stale_days
    threshold_alloc = settings.allocation_stale_days

    rows = []
    for p in people:
        oo_ctx = _one_on_one_context(p.last_one_on_one_date, p.next_one_on_one_date, threshold_oo)
        if p.current_allocation_type is not None:
            alloc_ctx = _alloc_context(p.current_allocation_confirmed_date, threshold_alloc)
        else:
            alloc_ctx = {"alloc_stale_days": None}

        rows.append(
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "seniority": p.seniority,
                "open_action_items_count": p.open_action_items_count,
                "current_allocation_type": p.current_allocation_type,
                "current_allocation_label": p.current_allocation_label,
                "alloc_stale_days": alloc_ctx["alloc_stale_days"],
                **oo_ctx,
            }
        )

    return templates.TemplateResponse(
        request,
        "people_list.html",
        {"people": rows, **_backup_context()},
    )


@router.get("/people/{person_id}", response_class=HTMLResponse)
async def person_detail(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    try:
        overview = await get_person_overview(conn, person_id, owner_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Person not found")

    today = date.today()
    threshold_oo = settings.one_on_one_stale_days
    threshold_alloc = settings.allocation_stale_days

    # Next 1:1 days until
    next_oo_days = None
    if overview.next_one_on_one:
        d = overview.next_one_on_one.scheduled_date
        if isinstance(d, str):
            d = date.fromisoformat(d)
        next_oo_days = max((d - today).days, 0)

    # Last 1:1 overdue check
    last_oo_days_ago = None
    last_oo_overdue = False
    if overview.last_one_on_one_date:
        d = overview.last_one_on_one_date
        if isinstance(d, str):
            d = date.fromisoformat(d)
        last_oo_days_ago = (today - d).days
        last_oo_overdue = last_oo_days_ago > threshold_oo

    # Allocation staleness
    alloc_stale = False
    alloc_days_since = None
    if overview.current_allocation and overview.current_allocation.last_confirmed_date:
        d = overview.current_allocation.last_confirmed_date
        if isinstance(d, str):
            d = date.fromisoformat(str(d))
        alloc_days_since = (today - d).days
        alloc_stale = alloc_days_since > threshold_alloc

    # Compute overdue flag for each action item
    enriched_items = []
    for item in overview.open_action_items:
        is_overdue = False
        if item.due_date:
            due = item.due_date
            if isinstance(due, str):
                due = date.fromisoformat(due)
            is_overdue = due < today
        enriched_items.append({"item": item, "is_overdue": is_overdue})

    return templates.TemplateResponse(
        request,
        "person_detail.html",
        {
            "overview": overview,
            "enriched_items": enriched_items,
            "next_oo_days": next_oo_days,
            "last_oo_days_ago": last_oo_days_ago,
            "last_oo_overdue": last_oo_overdue,
            "alloc_stale": alloc_stale,
            "alloc_days_since": alloc_days_since,
            **_backup_context(),
        },
    )


@router.post("/action-items/{action_item_id}/complete", response_class=HTMLResponse)
async def complete_action_item_htmx(
    request: Request,
    action_item_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    try:
        item = await complete_action_item(conn, action_item_id, owner_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Action item not found")

    return templates.TemplateResponse(
        request,
        "fragments/action_item_done.html",
        {"item_id": item.id, "item_text": item.text},
    )


@router.get("/people/{person_id}/allocation-history", response_class=HTMLResponse)
async def allocation_history_fragment(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    result = await conn.execute(
        text(
            "SELECT * FROM allocations"
            " WHERE person_id = :pid AND owner_id = :owner"
            " ORDER BY start_date DESC"
        ),
        {"pid": person_id, "owner": owner_id},
    )
    from cadencia.services.allocations import _row_to_allocation

    allocations = [_row_to_allocation(r) for r in result.fetchall()]
    return templates.TemplateResponse(
        request,
        "fragments/allocation_history.html",
        {"allocations": allocations},
    )


@router.get("/people/{person_id}/full-log", response_class=HTMLResponse)
async def full_log_fragment(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    result = await conn.execute(
        text(
            "SELECT * FROM one_on_ones"
            " WHERE person_id = :pid AND owner_id = :owner AND completed = 1"
            " ORDER BY scheduled_date DESC"
        ),
        {"pid": person_id, "owner": owner_id},
    )
    from cadencia.services.one_on_ones import _row_to_one_on_one

    one_on_ones = [_row_to_one_on_one(r) for r in result.fetchall()]
    return templates.TemplateResponse(
        request,
        "fragments/full_log.html",
        {"one_on_ones": one_on_ones},
    )
