"""Cross-table derived queries: the Monday-morning entry points."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.config import settings
from cadencia.models.queries import (
    OneOnOnePrep,
    OverdueActionItem,
    OverdueOneOnOne,
    PersonOverview,
    StaleAllocation,
    StaleFeedback,
    StalenessReport,
)
from cadencia.services.action_items import get_open_action_items
from cadencia.services.activities import list_active_activities
from cadencia.services.allocations import get_current_allocation
from cadencia.services.observations import list_observations
from cadencia.services.one_on_ones import _row_to_one_on_one, get_last_one_on_one
from cadencia.services.people import get_person
from cadencia.services.scheduling import next_expected_one_on_one


async def whats_stale(
    conn: AsyncConnection,
    owner_id: str = "default",
    allocation_threshold_days: int = 45,
    one_on_one_threshold_days: int = 14,
) -> StalenessReport:
    today = date.today()
    alloc_cutoff = (today - timedelta(days=allocation_threshold_days)).isoformat()

    # Stale allocations
    result = await conn.execute(
        text(
            "SELECT p.id, p.name, a.last_confirmed_date, a.type"
            " FROM people p"
            " LEFT JOIN allocations a ON a.person_id = p.id AND a.end_date IS NULL"
            " WHERE p.owner_id = :owner AND p.status = 'active'"
            "   AND (a.last_confirmed_date IS NULL OR a.last_confirmed_date < :cutoff)"
            " ORDER BY a.last_confirmed_date ASC NULLS FIRST"
        ),
        {"owner": owner_id, "cutoff": alloc_cutoff},
    )
    stale_allocs = []
    for row in result.fetchall():
        r = dict(row._mapping)
        if r["last_confirmed_date"]:
            days = (today - date.fromisoformat(r["last_confirmed_date"])).days
        else:
            days = 9999
        stale_allocs.append(
            StaleAllocation(
                person_id=r["id"],
                person_name=r["name"],
                days_since_confirmed=days,
                current_allocation_type=r.get("type"),
            )
        )

    # Overdue 1:1s: each person's threshold = COALESCE(their cadence, global default)
    result = await conn.execute(
        text(
            "SELECT p.id, p.name, p.one_on_one_cadence_days,"
            "  MAX(CASE WHEN o.completed = 1 THEN o.scheduled_date END) AS last_oo,"
            "  MIN(CASE WHEN o.completed = 0 THEN o.scheduled_date END) AS next_oo"
            " FROM people p"
            " LEFT JOIN one_on_ones o ON o.person_id = p.id AND o.owner_id = :owner"
            " WHERE p.owner_id = :owner AND p.status = 'active'"
            " GROUP BY p.id, p.name, p.one_on_one_cadence_days"
            " HAVING last_oo IS NULL"
            "     OR last_oo < date('now', '-' ||"
            "        CAST(COALESCE(p.one_on_one_cadence_days, :global_oo) AS TEXT)"
            "        || ' days')"
            " ORDER BY last_oo ASC NULLS FIRST"
        ),
        {"owner": owner_id, "global_oo": one_on_one_threshold_days},
    )
    overdue_oos = []
    for row in result.fetchall():
        r = dict(row._mapping)
        if r["last_oo"]:
            days = (today - date.fromisoformat(r["last_oo"])).days
        else:
            days = None
        overdue_oos.append(
            OverdueOneOnOne(
                person_id=r["id"],
                person_name=r["name"],
                days_since_last_one_on_one=days,
                next_scheduled=date.fromisoformat(r["next_oo"]) if r["next_oo"] else None,
            )
        )

    # Overdue action items
    result = await conn.execute(
        text(
            "SELECT a.id, a.text, a.due_date, p.name AS person_name"
            " FROM action_items a"
            " JOIN people p ON a.person_id = p.id"
            " WHERE a.owner_id = :owner AND a.status = 'open'"
            "   AND a.due_date IS NOT NULL AND a.due_date < :today"
            " ORDER BY a.due_date ASC"
        ),
        {"owner": owner_id, "today": today.isoformat()},
    )
    overdue_ais = []
    for row in result.fetchall():
        r = dict(row._mapping)
        due = date.fromisoformat(r["due_date"])
        overdue_ais.append(
            OverdueActionItem(
                action_item_id=r["id"],
                person_name=r["person_name"],
                text=r["text"],
                due_date=due,
                days_overdue=(today - due).days,
            )
        )

    # Stale stakeholder feedback
    feedback_cutoff = (today - timedelta(days=settings.stakeholder_feedback_stale_days)).isoformat()
    result = await conn.execute(
        text(
            "SELECT p.id, p.name, MAX(sf.received_date) AS last_feedback"
            " FROM people p"
            " LEFT JOIN stakeholder_feedback sf"
            "   ON sf.person_id = p.id AND sf.owner_id = :owner"
            " WHERE p.owner_id = :owner AND p.status = 'active'"
            " GROUP BY p.id, p.name"
            " HAVING last_feedback IS NULL OR last_feedback < :cutoff"
            " ORDER BY last_feedback ASC NULLS FIRST"
        ),
        {"owner": owner_id, "cutoff": feedback_cutoff},
    )
    stale_feedback = []
    for row in result.fetchall():
        r = dict(row._mapping)
        if r["last_feedback"]:
            days = (today - date.fromisoformat(r["last_feedback"])).days
        else:
            days = None
        stale_feedback.append(
            StaleFeedback(
                person_id=r["id"],
                person_name=r["name"],
                days_since_last_feedback=days,
            )
        )

    return StalenessReport(
        stale_allocations=stale_allocs,
        overdue_one_on_ones=overdue_oos,
        overdue_action_items=overdue_ais,
        stale_feedback=stale_feedback,
    )


async def prepare_one_on_one(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
) -> OneOnOnePrep:
    person = await get_person(conn, person_id, owner_id)
    ninety_days_ago = (
        datetime.now(UTC) - timedelta(days=90)
    ).isoformat()

    last_oo = await get_last_one_on_one(conn, person_id, owner_id)
    open_ais = await get_open_action_items(conn, owner_id, person_id)
    recent_obs = await list_observations(
        conn, person_id, owner_id, since=ninety_days_ago
    )

    return OneOnOnePrep(
        person_id=person_id,
        person_name=person.name,
        last_one_on_one=last_oo,
        open_action_items=open_ais,
        recent_observations=recent_obs,
    )


async def get_person_overview(
    conn: AsyncConnection,
    person_id: str,
    owner_id: str = "default",
    include_sensitive: bool = False,
) -> PersonOverview:
    person = await get_person(conn, person_id, owner_id)
    ninety_days_ago = (
        datetime.now(UTC) - timedelta(days=90)
    ).isoformat()

    current_alloc = await get_current_allocation(conn, person_id, owner_id)
    open_ais = await get_open_action_items(conn, owner_id, person_id)
    last_oo = await get_last_one_on_one(conn, person_id, owner_id)
    recent_obs = await list_observations(
        conn, person_id, owner_id,
        since=ninety_days_ago,
        include_sensitive=include_sensitive,
    )
    active_activities = await list_active_activities(conn, person_id, owner_id)

    # Next scheduled (uncompleted) 1:1
    result = await conn.execute(
        text(
            "SELECT * FROM one_on_ones"
            " WHERE person_id = :pid AND owner_id = :owner AND completed = 0"
            "   AND scheduled_date >= date('now')"
            " ORDER BY scheduled_date ASC LIMIT 1"
        ),
        {"pid": person_id, "owner": owner_id},
    )
    next_oo_row = result.fetchone()
    next_oo = _row_to_one_on_one(next_oo_row) if next_oo_row else None

    # Compute next expected 1:1 date
    _cadence = person.one_on_one_cadence_days or settings.one_on_one_stale_days
    _last = last_oo.scheduled_date if last_oo else None
    if _last:
        if isinstance(_last, str):
            _last = date.fromisoformat(_last)
        _next_expected = next_expected_one_on_one(
            _last,
            _cadence,
            weekday=person.recurrence_weekday,
            week_of_month=person.recurrence_week_of_month,
        )
    elif next_oo:
        _next_expected = next_oo.scheduled_date
        if isinstance(_next_expected, str):
            _next_expected = date.fromisoformat(str(_next_expected))
    else:
        _next_expected = None

    return PersonOverview(
        person_id=person_id,
        name=person.name,
        role=person.role,
        seniority=person.seniority,
        start_date=person.start_date,
        status=person.status,
        one_on_one_cadence_days=person.one_on_one_cadence_days,
        recurrence_weekday=person.recurrence_weekday,
        recurrence_week_of_month=person.recurrence_week_of_month,
        current_allocation=current_alloc,
        open_action_items=open_ais,
        next_one_on_one=next_oo,
        last_one_on_one_date=last_oo.scheduled_date if last_oo else None,
        recent_observations=recent_obs,
        next_expected_date=_next_expected,
        active_activities=active_activities,
    )
