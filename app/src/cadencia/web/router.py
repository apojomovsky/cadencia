"""Web UI routes: server-rendered HTML via Jinja2 + HTMX."""

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.api.deps import get_backup_status, get_db, get_owner_id
from cadencia.config import settings
from cadencia.models.feedback import AddFeedbackInput
from cadencia.models.people import CreatePersonInput
from cadencia.models.stakeholders import CreateStakeholderInput
from cadencia.services.action_items import complete_action_item
from cadencia.services.exceptions import NotFoundError
from cadencia.services.feedback import add_feedback, list_feedback_for_person
from cadencia.services.people import (
    create_person,
    get_person,
    list_people,
    set_one_on_one_cadence,
    update_person_full,
)
from cadencia.services.queries import get_person_overview, whats_stale
from cadencia.services.stakeholders import create_stakeholder, get_stakeholder
from cadencia.services.stakeholders import list_stakeholders as list_stakeholders_svc
from cadencia.services.stakeholders import update_stakeholder as update_stakeholder_svc

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
            "stale_feedback": report.stale_feedback,
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
        effective_oo = p.one_on_one_cadence_days or threshold_oo
        # Use explicit scheduled date if present, fall back to expected
        next_date = p.next_one_on_one_date or p.next_expected_date
        oo_ctx = _one_on_one_context(p.last_one_on_one_date, next_date, effective_oo)
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
                "current_allocation_percent": p.current_allocation_percent,
                "current_allocation_label": p.current_allocation_label,
                "alloc_stale_days": alloc_ctx["alloc_stale_days"],
                "active_activity_roles": p.active_activity_roles,
                **oo_ctx,
            }
        )

    return templates.TemplateResponse(
        request,
        "people_list.html",
        {"people": rows, **_backup_context()},
    )


@router.get("/people/new", response_class=HTMLResponse)
async def people_new_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "people_new.html",
        {**_backup_context()},
    )


@router.post("/people", response_class=HTMLResponse)
async def people_create(
    request: Request,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> RedirectResponse:
    form = await request.form()

    def _opt(key: str) -> str | None:
        v = str(form.get(key, "")).strip()
        return v or None

    def _int_opt(key: str) -> int | None:
        v = str(form.get(key, "")).strip()
        return int(v) if v else None

    start_raw = _opt("start_date")
    from datetime import date as _date
    data = CreatePersonInput(
        name=str(form.get("name", "")).strip(),
        role=_opt("role"),
        seniority=_opt("seniority"),  # type: ignore[arg-type]
        start_date=_date.fromisoformat(start_raw) if start_raw else None,
        one_on_one_cadence_days=_int_opt("one_on_one_cadence_days"),
        recurrence_weekday=_int_opt("recurrence_weekday"),
        recurrence_week_of_month=_int_opt("recurrence_week_of_month"),
    )
    person = await create_person(conn, data, owner_id, source="web")
    return RedirectResponse(f"/people/{person.id}", status_code=303)


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
    threshold_alloc = settings.allocation_stale_days
    # Per-person cadence with global fallback
    effective_oo_threshold = overview.one_on_one_cadence_days or settings.one_on_one_stale_days

    # Next 1:1 days until
    next_oo_days = None
    if overview.next_expected_date:
        d = overview.next_expected_date
        if isinstance(d, str):
            d = date.fromisoformat(str(d))
        next_oo_days = (d - today).days  # can be negative = overdue

    # Last 1:1 overdue check
    last_oo_days_ago = None
    last_oo_overdue = False
    if overview.last_one_on_one_date:
        d = overview.last_one_on_one_date
        if isinstance(d, str):
            d = date.fromisoformat(d)
        last_oo_days_ago = (today - d).days
        last_oo_overdue = last_oo_days_ago > effective_oo_threshold

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

    recent_feedback = await list_feedback_for_person(conn, person_id, owner_id, limit=5)
    all_stakeholders = await list_stakeholders_svc(conn, owner_id)

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
            "global_oo_cadence": settings.one_on_one_stale_days,
            "recent_feedback": recent_feedback,
            "all_stakeholders": all_stakeholders,
            "recurrence_weekday": overview.recurrence_weekday,
            "recurrence_week_of_month": overview.recurrence_week_of_month,
            **_backup_context(),
        },
    )


@router.get("/people/{person_id}/edit", response_class=HTMLResponse)
async def person_edit_form(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    try:
        person = await get_person(conn, person_id, owner_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Person not found")
    return templates.TemplateResponse(
        request,
        "person_edit.html",
        {"person": person, "global_oo_cadence": settings.one_on_one_stale_days,
         **_backup_context()},
    )


@router.post("/people/{person_id}/edit", response_class=HTMLResponse)
async def person_edit_save(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> RedirectResponse:
    form = await request.form()

    def _opt(key: str) -> str | None:
        v = str(form.get(key, "")).strip()
        return v or None

    def _int_opt(key: str) -> int | None:
        v = str(form.get(key, "")).strip()
        return int(v) if v else None

    start_raw = _opt("start_date")
    from datetime import date as _date
    try:
        await update_person_full(
            conn,
            person_id,
            name=str(form.get("name", "")).strip(),
            role=_opt("role"),
            seniority=_opt("seniority"),
            start_date=_date.fromisoformat(start_raw) if start_raw else None,
            status=str(form.get("status", "active")),
            recurrence_weekday=_int_opt("recurrence_weekday"),
            recurrence_week_of_month=_int_opt("recurrence_week_of_month"),
            owner_id=owner_id,
            source="web",
        )
        await set_one_on_one_cadence(
            conn, person_id, _int_opt("one_on_one_cadence_days"), owner_id, source="web"
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Person not found")
    return RedirectResponse(f"/people/{person_id}", status_code=303)


@router.post("/people/{person_id}/archive", response_class=HTMLResponse)
async def person_archive(
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> RedirectResponse:
    try:
        person = await get_person(conn, person_id, owner_id)
        await update_person_full(
            conn,
            person_id,
            name=person.name,
            role=person.role,
            seniority=person.seniority,
            start_date=person.start_date,
            status="left",
            recurrence_weekday=person.recurrence_weekday,
            recurrence_week_of_month=person.recurrence_week_of_month,
            owner_id=owner_id,
            source="web",
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Person not found")
    return RedirectResponse("/people", status_code=303)


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


@router.get("/people/{person_id}/cadence-display", response_class=HTMLResponse)
async def cadence_display_fragment(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    try:
        person = await get_person(conn, person_id, owner_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Person not found")
    return templates.TemplateResponse(
        request,
        "fragments/cadence_display.html",
        {
            "person_id": person_id,
            "cadence_days": person.one_on_one_cadence_days,
            "global_default": settings.one_on_one_stale_days,
        },
    )


@router.get("/people/{person_id}/cadence-edit-form", response_class=HTMLResponse)
async def cadence_edit_form_fragment(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    try:
        person = await get_person(conn, person_id, owner_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Person not found")
    return templates.TemplateResponse(
        request,
        "fragments/cadence_edit_form.html",
        {
            "person_id": person_id,
            "cadence_days": person.one_on_one_cadence_days,
            "global_default": settings.one_on_one_stale_days,
        },
    )


@router.post("/people/{person_id}/add-feedback", response_class=HTMLResponse)
async def add_feedback_htmx(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    form = await request.form()
    content = str(form.get("content", "")).strip()
    stakeholder_id_raw = form.get("stakeholder_id", "")
    stakeholder_id = str(stakeholder_id_raw) if stakeholder_id_raw else None
    if not content:
        raise HTTPException(status_code=400, detail="Content required")
    data = AddFeedbackInput(
        person_id=person_id,
        stakeholder_id=stakeholder_id,
        content=content,
    )
    await add_feedback(conn, data, owner_id)
    recent = await list_feedback_for_person(conn, person_id, owner_id, limit=5)
    all_stakeholders = await list_stakeholders_svc(conn, owner_id)
    return templates.TemplateResponse(
        request,
        "fragments/feedback_section.html",
        {"person_id": person_id, "recent_feedback": recent, "all_stakeholders": all_stakeholders},
    )


@router.get("/stakeholders", response_class=HTMLResponse)
async def stakeholders_list(
    request: Request,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    stakeholders = await list_stakeholders_svc(conn, owner_id)
    return templates.TemplateResponse(
        request,
        "stakeholders.html",
        {"stakeholders": stakeholders, **_backup_context()},
    )


@router.post("/stakeholders", response_class=HTMLResponse)
async def stakeholders_create(
    request: Request,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    form = await request.form()
    raw_aliases = str(form.get("aliases", "")).strip()
    aliases = [a.strip() for a in raw_aliases.split(",") if a.strip()]
    data = CreateStakeholderInput(
        name=str(form.get("name", "")),
        type=str(form.get("type", "other")),  # type: ignore[arg-type]
        organization=str(form.get("organization", "")) or None,
        aliases=aliases,
    )
    await create_stakeholder(conn, data, owner_id)
    return RedirectResponse("/stakeholders", status_code=303)


@router.get("/stakeholders/{stakeholder_id}/edit", response_class=HTMLResponse)
async def stakeholder_edit_form(
    request: Request,
    stakeholder_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    try:
        stakeholder = await get_stakeholder(conn, stakeholder_id, owner_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stakeholder not found")
    return templates.TemplateResponse(
        request,
        "stakeholder_edit.html",
        {"stakeholder": stakeholder, **_backup_context()},
    )


@router.post("/stakeholders/{stakeholder_id}", response_class=HTMLResponse)
async def stakeholder_edit_save(
    request: Request,
    stakeholder_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> RedirectResponse:
    form = await request.form()
    raw_aliases = str(form.get("aliases", "")).strip()
    aliases = [a.strip() for a in raw_aliases.split(",") if a.strip()]
    from cadencia.models.stakeholders import UpdateStakeholderInput
    data = UpdateStakeholderInput(
        name=str(form.get("name", "")).strip() or None,
        type=str(form.get("type", "")).strip() or None,  # type: ignore[arg-type]
        organization=str(form.get("organization", "")).strip() or None,
        aliases=aliases,
    )
    try:
        await update_stakeholder_svc(conn, stakeholder_id, data, owner_id, source="web")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stakeholder not found")
    return RedirectResponse("/stakeholders", status_code=303)


@router.post("/people/{person_id}/set-cadence", response_class=HTMLResponse)
async def set_cadence_htmx(
    request: Request,
    person_id: str,
    conn: AsyncConnection = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
) -> HTMLResponse:
    form = await request.form()
    raw = form.get("cadence_days", "")
    cadence_days = int(raw) if raw else None
    try:
        updated = await set_one_on_one_cadence(conn, person_id, cadence_days, owner_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Person not found")
    return templates.TemplateResponse(
        request,
        "fragments/cadence_display.html",
        {
            "person_id": person_id,
            "cadence_days": updated.one_on_one_cadence_days,
            "global_default": settings.one_on_one_stale_days,
        },
    )
