# Stakeholder Edit + Aliases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stakeholder aliases (alternate names) stored as a JSON array, a web edit page for stakeholders, and a `find_stakeholder` MCP tool that resolves by name or alias.

**Architecture:** Aliases live in a new `aliases` TEXT column on the `stakeholders` table (JSON array, same pattern as `tags` on observations). The service layer parses/writes aliases via `json.loads`/`json.dumps`. A new `find_stakeholder_by_name_or_alias` service function searches name then aliases. The web UI gains an edit route and template; the MCP gains a `find_stakeholder` tool.

**Tech Stack:** Python, FastAPI, Jinja2, HTMX, SQLAlchemy async, SQLite (`json_each()`), pytest-asyncio.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/src/cadencia/db/sql/008_stakeholder_aliases.sql` | Create | Migration adding `aliases` column |
| `app/src/cadencia/models/stakeholders.py` | Modify | Add `aliases` field to all three models |
| `app/src/cadencia/services/stakeholders.py` | Modify | Parse/write aliases; add `find_stakeholder_by_name_or_alias` |
| `app/tests/services/test_stakeholders.py` | Modify | Tests for alias CRUD and find-by-alias |
| `app/src/cadencia/web/router.py` | Modify | Add GET/POST edit routes, import `update_stakeholder` |
| `app/src/cadencia/web/templates/stakeholders.html` | Modify | Show aliases in list, add aliases field to create form |
| `app/src/cadencia/web/templates/stakeholder_edit.html` | Create | Edit page for a single stakeholder |
| `mcp/src/cadencia_mcp/server.py` | Modify | Add `find_stakeholder` tool; include `aliases` in `list_stakeholders` output |

---

## Task 1: DB migration — add aliases column

**Files:**
- Create: `app/src/cadencia/db/sql/008_stakeholder_aliases.sql`

- [ ] **Step 1: Create the migration file**

```sql
ALTER TABLE stakeholders ADD COLUMN aliases TEXT NOT NULL DEFAULT '[]';
```

- [ ] **Step 2: Verify migration runs**

Run the test suite — the `conn` fixture applies all migrations on each test. If the migration file parses correctly, tests will pass.

```bash
cd app && python -m pytest tests/services/test_stakeholders.py -v
```

Expected: 3 tests pass (existing tests, no new column behaviour yet).

- [ ] **Step 3: Commit**

```bash
git add app/src/cadencia/db/sql/008_stakeholder_aliases.sql
git commit -m "feat(db): add aliases column to stakeholders table"
```

---

## Task 2: Model + service — aliases CRUD

**Files:**
- Modify: `app/src/cadencia/models/stakeholders.py`
- Modify: `app/src/cadencia/services/stakeholders.py`
- Test: `app/tests/services/test_stakeholders.py`

- [ ] **Step 1: Write failing tests**

Append to `app/tests/services/test_stakeholders.py`:

```python
async def test_create_stakeholder_with_aliases(conn: AsyncConnection) -> None:
    s = await create_stakeholder(
        conn, CreateStakeholderInput(name="Agustin Alba Chicar", aliases=["Agus"])
    )
    assert s.aliases == ["Agus"]


async def test_update_stakeholder_aliases(conn: AsyncConnection) -> None:
    s = await create_stakeholder(conn, CreateStakeholderInput(name="Gonzalo De Pedro"))
    updated = await update_stakeholder(
        conn, s.id, UpdateStakeholderInput(aliases=["Gonzo"])
    )
    assert updated.aliases == ["Gonzo"]


async def test_clear_stakeholder_aliases(conn: AsyncConnection) -> None:
    s = await create_stakeholder(
        conn, CreateStakeholderInput(name="Someone", aliases=["S"])
    )
    updated = await update_stakeholder(conn, s.id, UpdateStakeholderInput(aliases=[]))
    assert updated.aliases == []


async def test_update_aliases_does_not_touch_when_none(conn: AsyncConnection) -> None:
    s = await create_stakeholder(
        conn, CreateStakeholderInput(name="Persist", aliases=["P"])
    )
    updated = await update_stakeholder(conn, s.id, UpdateStakeholderInput(name="Persist 2"))
    assert updated.aliases == ["P"]
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd app && python -m pytest tests/services/test_stakeholders.py -v -k "aliases"
```

Expected: `TypeError` or `ValidationError` — `aliases` not yet a known field.

- [ ] **Step 3: Update models**

Replace `app/src/cadencia/models/stakeholders.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Stakeholder(BaseModel):
    id: str
    name: str
    type: Literal["am", "client", "internal", "other"]
    organization: str | None
    notes: str | None
    aliases: list[str]
    created_at: datetime
    updated_at: datetime


class CreateStakeholderInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["am", "client", "internal", "other"] = "other"
    organization: str | None = None
    notes: str | None = None
    aliases: list[str] = []


class UpdateStakeholderInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: Literal["am", "client", "internal", "other"] | None = None
    organization: str | None = None
    notes: str | None = None
    aliases: list[str] | None = None
```

- [ ] **Step 4: Update service**

Replace `app/src/cadencia/services/stakeholders.py`:

```python
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cadencia.models.stakeholders import CreateStakeholderInput, Stakeholder, UpdateStakeholderInput
from cadencia.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def _row_to_stakeholder(row: object) -> Stakeholder:
    r = dict(row._mapping)  # type: ignore[union-attr]
    return Stakeholder(
        id=r["id"],
        name=r["name"],
        type=r["type"],
        organization=r.get("organization"),
        notes=r.get("notes"),
        aliases=json.loads(r.get("aliases") or "[]"),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def list_stakeholders(
    conn: AsyncConnection,
    owner_id: str = "default",
) -> list[Stakeholder]:
    result = await conn.execute(
        text("SELECT * FROM stakeholders WHERE owner_id = :owner ORDER BY name"),
        {"owner": owner_id},
    )
    return [_row_to_stakeholder(r) for r in result.fetchall()]


async def get_stakeholder(
    conn: AsyncConnection,
    stakeholder_id: str,
    owner_id: str = "default",
) -> Stakeholder:
    result = await conn.execute(
        text("SELECT * FROM stakeholders WHERE id = :id AND owner_id = :owner"),
        {"id": stakeholder_id, "owner": owner_id},
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError("stakeholder", stakeholder_id)
    return _row_to_stakeholder(row)


async def find_stakeholder_by_name_or_alias(
    conn: AsyncConnection,
    query: str,
    owner_id: str = "default",
) -> list[Stakeholder]:
    """Return stakeholders whose name or any alias matches query (case-insensitive, exact)."""
    q = query.strip().lower()
    result = await conn.execute(
        text("""
            SELECT DISTINCT s.*
            FROM stakeholders s
            WHERE s.owner_id = :owner
              AND (
                lower(s.name) = :q
                OR EXISTS (
                    SELECT 1 FROM json_each(s.aliases) WHERE lower(value) = :q
                )
              )
            ORDER BY s.name
        """),
        {"owner": owner_id, "q": q},
    )
    return [_row_to_stakeholder(r) for r in result.fetchall()]


async def create_stakeholder(
    conn: AsyncConnection,
    data: CreateStakeholderInput,
    owner_id: str = "default",
    source: str = "api",
) -> Stakeholder:
    now = datetime.now(UTC).isoformat()
    sid = str(uuid.uuid4())
    await conn.execute(
        text(
            "INSERT INTO stakeholders (id, owner_id, name, type, organization, notes,"
            " aliases, created_at, updated_at)"
            " VALUES (:id, :owner, :name, :type, :org, :notes, :aliases, :now, :now)"
        ),
        {
            "id": sid,
            "owner": owner_id,
            "name": data.name,
            "type": data.type,
            "org": data.organization,
            "notes": data.notes,
            "aliases": json.dumps(data.aliases),
            "now": now,
        },
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "stakeholders",
                "operation": "insert",
                "record_id": sid,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_stakeholder(conn, sid, owner_id)


async def update_stakeholder(
    conn: AsyncConnection,
    stakeholder_id: str,
    data: UpdateStakeholderInput,
    owner_id: str = "default",
    source: str = "api",
) -> Stakeholder:
    await get_stakeholder(conn, stakeholder_id, owner_id)

    now = datetime.now(UTC).isoformat()
    updates: dict[str, object] = {"now": now, "id": stakeholder_id, "owner": owner_id}
    set_clauses: list[str] = ["updated_at = :now"]

    if data.name is not None:
        updates["name"] = data.name
        set_clauses.append("name = :name")
    if data.type is not None:
        updates["type"] = data.type
        set_clauses.append("type = :type")
    if data.organization is not None:
        updates["organization"] = data.organization
        set_clauses.append("organization = :organization")
    if data.notes is not None:
        updates["notes"] = data.notes
        set_clauses.append("notes = :notes")
    if data.aliases is not None:
        updates["aliases"] = json.dumps(data.aliases)
        set_clauses.append("aliases = :aliases")

    await conn.execute(
        text(
            f"UPDATE stakeholders SET {', '.join(set_clauses)}"
            " WHERE id = :id AND owner_id = :owner"
        ),
        updates,
    )
    logger.info(
        json.dumps(
            {
                "event": "write",
                "table": "stakeholders",
                "operation": "update",
                "record_id": stakeholder_id,
                "source": source,
                "ts": now,
            }
        )
    )
    return await get_stakeholder(conn, stakeholder_id, owner_id)
```

- [ ] **Step 5: Run tests**

```bash
cd app && python -m pytest tests/services/test_stakeholders.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/src/cadencia/models/stakeholders.py \
        app/src/cadencia/services/stakeholders.py \
        app/tests/services/test_stakeholders.py
git commit -m "feat(stakeholders): add aliases field with CRUD and find-by-alias"
```

---

## Task 3: find_stakeholder_by_name_or_alias tests (find function)

**Files:**
- Test: `app/tests/services/test_stakeholders.py`

- [ ] **Step 1: Write failing tests for find function**

Append to `app/tests/services/test_stakeholders.py`:

```python
from cadencia.services.stakeholders import find_stakeholder_by_name_or_alias


async def test_find_by_name(conn: AsyncConnection) -> None:
    await create_stakeholder(conn, CreateStakeholderInput(name="Gonzalo De Pedro"))
    results = await find_stakeholder_by_name_or_alias(conn, "Gonzalo De Pedro")
    assert len(results) == 1
    assert results[0].name == "Gonzalo De Pedro"


async def test_find_by_alias(conn: AsyncConnection) -> None:
    await create_stakeholder(
        conn, CreateStakeholderInput(name="Gonzalo De Pedro", aliases=["Gonzo"])
    )
    results = await find_stakeholder_by_name_or_alias(conn, "Gonzo")
    assert len(results) == 1
    assert results[0].name == "Gonzalo De Pedro"


async def test_find_case_insensitive(conn: AsyncConnection) -> None:
    await create_stakeholder(
        conn, CreateStakeholderInput(name="Gonzalo De Pedro", aliases=["Gonzo"])
    )
    assert len(await find_stakeholder_by_name_or_alias(conn, "gonzo")) == 1
    assert len(await find_stakeholder_by_name_or_alias(conn, "GONZALO DE PEDRO")) == 1


async def test_find_no_match(conn: AsyncConnection) -> None:
    await create_stakeholder(conn, CreateStakeholderInput(name="Someone"))
    results = await find_stakeholder_by_name_or_alias(conn, "Nobody")
    assert results == []
```

- [ ] **Step 2: Run tests**

```bash
cd app && python -m pytest tests/services/test_stakeholders.py -v -k "find"
```

Expected: all 4 find tests pass (function was already implemented in Task 2).

- [ ] **Step 3: Commit**

```bash
git add app/tests/services/test_stakeholders.py
git commit -m "test(stakeholders): add find_stakeholder_by_name_or_alias tests"
```

---

## Task 4: Web — stakeholder edit routes + template

**Files:**
- Modify: `app/src/cadencia/web/router.py`
- Create: `app/src/cadencia/web/templates/stakeholder_edit.html`

- [ ] **Step 1: Add import for update_stakeholder in router.py**

Find this line in `app/src/cadencia/web/router.py`:

```python
from cadencia.services.stakeholders import create_stakeholder
from cadencia.services.stakeholders import list_stakeholders as list_stakeholders_svc
```

Replace with:

```python
from cadencia.services.stakeholders import create_stakeholder
from cadencia.services.stakeholders import get_stakeholder
from cadencia.services.stakeholders import list_stakeholders as list_stakeholders_svc
from cadencia.services.stakeholders import update_stakeholder as update_stakeholder_svc
```

- [ ] **Step 2: Add edit routes to router.py**

Find the existing `stakeholders_create` route (ends with `return RedirectResponse("/stakeholders", status_code=303)`). After its closing line, add:

```python
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
        notes=str(form.get("notes", "")).strip() or None,
        aliases=aliases,
    )
    try:
        await update_stakeholder_svc(conn, stakeholder_id, data, owner_id, source="web")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stakeholder not found")
    return RedirectResponse("/stakeholders", status_code=303)
```

- [ ] **Step 3: Create stakeholder_edit.html**

Create `app/src/cadencia/web/templates/stakeholder_edit.html`:

```html
{% extends "base.html" %}
{% block title %}Edit {{ stakeholder.name }} | Cadencia{% endblock %}
{% block nav_stakeholders %}active{% endblock %}

{% block content %}
<a class="back-link" href="/stakeholders">&larr; Stakeholders</a>
<h2 style="margin-bottom: 24px;">Edit {{ stakeholder.name }}</h2>

<form class="person-form" method="post" action="/stakeholders/{{ stakeholder.id }}">
  <div class="field">
    <label for="name">Name *</label>
    <input id="name" type="text" name="name" required value="{{ stakeholder.name }}">
  </div>
  <div class="field">
    <label for="type">Type</label>
    <select id="type" name="type">
      <option value="am" {% if stakeholder.type == "am" %}selected{% endif %}>Account Manager</option>
      <option value="client" {% if stakeholder.type == "client" %}selected{% endif %}>Client</option>
      <option value="internal" {% if stakeholder.type == "internal" %}selected{% endif %}>Internal</option>
      <option value="other" {% if stakeholder.type == "other" %}selected{% endif %}>Other</option>
    </select>
  </div>
  <div class="field">
    <label for="organization">Organization</label>
    <input id="organization" type="text" name="organization" value="{{ stakeholder.organization or '' }}">
  </div>
  <div class="field">
    <label for="aliases">Also known as</label>
    <input id="aliases" type="text" name="aliases"
      placeholder="Comma-separated, e.g. Agus, Agus Alba"
      value="{{ stakeholder.aliases | join(', ') }}">
  </div>
  <div class="field">
    <label for="notes">Notes</label>
    <input id="notes" type="text" name="notes" value="{{ stakeholder.notes or '' }}">
  </div>
  <div class="form-actions">
    <button type="submit" class="btn btn-primary">Save changes</button>
    <a href="/stakeholders" class="btn">Cancel</a>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 4: Rebuild and verify in browser**

```bash
docker compose build app && docker compose up -d app
```

Open http://localhost:8080/stakeholders — click any stakeholder row (not yet a link, see Task 5). Navigate directly to http://localhost:8080/stakeholders/<any-id>/edit — the edit form should render with the stakeholder's current values. Submit the form, verify redirect to `/stakeholders`.

- [ ] **Step 5: Commit**

```bash
git add app/src/cadencia/web/router.py \
        app/src/cadencia/web/templates/stakeholder_edit.html
git commit -m "feat(web): add stakeholder edit page"
```

---

## Task 5: Web — aliases in list + edit link + create form aliases field

**Files:**
- Modify: `app/src/cadencia/web/templates/stakeholders.html`

- [ ] **Step 1: Update stakeholders.html**

Replace the full file:

```html
{% extends "base.html" %}
{% block title %}Stakeholders | Cadencia{% endblock %}
{% block nav_stakeholders %}active{% endblock %}

{% block content %}
<div class="list-header">
  <h2>Stakeholders</h2>
</div>

{% if stakeholders %}
<div class="people-list" style="margin-bottom: 24px;">
  {% for s in stakeholders %}
  <a class="person-row" href="/stakeholders/{{ s.id }}/edit">
    <div class="person-info">
      <div class="person-name">{{ s.name }}</div>
      {% if s.aliases %}
      <div class="person-role">{{ s.aliases | join(', ') }}</div>
      {% endif %}
    </div>
    <span class="badge muted">{{ s.type }}</span>
    {% if s.organization %}<span class="badge muted">{{ s.organization }}</span>{% endif %}
  </a>
  {% endfor %}
</div>
{% else %}
<p class="empty" style="margin-bottom: 24px;">No stakeholders yet.</p>
{% endif %}

<div class="section">
  <div class="section-header">Add Stakeholder</div>
  <div class="section-body">
    <form class="person-form" method="post" action="/stakeholders" style="max-width:400px;">
      <div class="field">
        <label for="name">Name *</label>
        <input id="name" type="text" name="name" required placeholder="Full name">
      </div>
      <div class="field">
        <label for="type">Type</label>
        <select id="type" name="type">
          <option value="am">Account Manager</option>
          <option value="client">Client</option>
          <option value="internal">Internal</option>
          <option value="other" selected>Other</option>
        </select>
      </div>
      <div class="field">
        <label for="organization">Organization</label>
        <input id="organization" type="text" name="organization" placeholder="Optional">
      </div>
      <div class="field">
        <label for="aliases">Also known as</label>
        <input id="aliases" type="text" name="aliases" placeholder="Comma-separated nicknames, e.g. Agus, Gonzo">
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary">Add</button>
      </div>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Update the create route in router.py to parse aliases**

Find the `stakeholders_create` route in `app/src/cadencia/web/router.py`. It currently reads form fields like:

```python
data = CreateStakeholderInput(
    name=...,
    type=...,
    organization=...,
    notes=...,
)
```

Replace the `data = CreateStakeholderInput(...)` block with:

```python
raw_aliases = str(form.get("aliases", "")).strip()
aliases = [a.strip() for a in raw_aliases.split(",") if a.strip()]
data = CreateStakeholderInput(
    name=str(form.get("name", "")).strip(),
    type=str(form.get("type", "other")),  # type: ignore[arg-type]
    organization=str(form.get("organization", "")).strip() or None,
    notes=str(form.get("notes", "")).strip() or None,
    aliases=aliases,
)
```

- [ ] **Step 3: Rebuild and verify in browser**

```bash
docker compose build app && docker compose up -d app
```

Open http://localhost:8080/stakeholders:
- Each stakeholder row is now a clickable link to its edit page
- Aliases appear below the name in muted text
- The create form has an "Also known as" field
- Add a stakeholder with aliases, verify they appear in the list
- Click a row, edit aliases, save, verify changes persist

- [ ] **Step 4: Commit**

```bash
git add app/src/cadencia/web/templates/stakeholders.html \
        app/src/cadencia/web/router.py
git commit -m "feat(web): show aliases in stakeholder list, add aliases to create form"
```

---

## Task 6: MCP — find_stakeholder tool + aliases in list_stakeholders

**Files:**
- Modify: `mcp/src/cadencia_mcp/server.py`

- [ ] **Step 1: Add import for find_stakeholder_by_name_or_alias**

Find this block near the top of `mcp/src/cadencia_mcp/server.py`:

```python
from cadencia.services.stakeholders import list_stakeholders as svc_list_stakeholders
from cadencia.services.stakeholders import update_stakeholder as svc_update_stakeholder
```

Replace with:

```python
from cadencia.services.stakeholders import find_stakeholder_by_name_or_alias as svc_find_stakeholder
from cadencia.services.stakeholders import list_stakeholders as svc_list_stakeholders
from cadencia.services.stakeholders import update_stakeholder as svc_update_stakeholder
```

- [ ] **Step 2: Update list_stakeholders to include aliases**

Find the `list_stakeholders` tool (around line 376). Its return block currently is:

```python
    return [
        {
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "organization": s.organization,
        }
        for s in stakeholders
    ]
```

Replace with:

```python
    return [
        {
            "id": s.id,
            "name": s.name,
            "aliases": s.aliases,
            "type": s.type,
            "organization": s.organization,
        }
        for s in stakeholders
    ]
```

- [ ] **Step 3: Add find_stakeholder tool**

After the `list_stakeholders` tool's closing brace, add:

```python
@mcp.tool()
async def find_stakeholder(name_or_alias: str) -> list[dict[str, Any]]:
    """Find stakeholders by name or alias (case-insensitive exact match).

    Use this to resolve a person's name or nickname to a stakeholder ID
    before calling other tools that require a stakeholder_id.

    name_or_alias: the name or alias to search for, e.g. "Gonzo" or "Gonzalo De Pedro".
    """
    async with get_connection() as conn:
        stakeholders = await svc_find_stakeholder(conn, name_or_alias, settings.owner_id)
    return [
        {
            "id": s.id,
            "name": s.name,
            "aliases": s.aliases,
            "type": s.type,
            "organization": s.organization,
        }
        for s in stakeholders
    ]
```

- [ ] **Step 4: Rebuild MCP and verify**

```bash
docker compose build app && docker compose up -d app
```

The MCP server shares the app image. After rebuild, verify the MCP server lists the new tool by checking Claude Code's MCP tool list (run `/mcp` in Claude Code, or restart the MCP connection and look for `find_stakeholder` in the tool list).

- [ ] **Step 5: Commit**

```bash
git add mcp/src/cadencia_mcp/server.py
git commit -m "feat(mcp): add find_stakeholder tool and aliases to list_stakeholders output"
```

---

## Task 7: Full regression check

No file changes. Verify nothing regressed.

- [ ] **Step 1: Run full test suite**

```bash
cd app && python -m pytest -v
```

Expected: all tests pass (44 existing + 8 new = 52 total).

- [ ] **Step 2: Smoke-check the UI**

- http://localhost:8080/stakeholders — list loads, rows are links
- Click a stakeholder — edit page renders with current values
- Edit name, aliases — save, verify list reflects changes
- Add new stakeholder with aliases from the create form
- http://localhost:8080/people — no regressions (feedback section still shows stakeholder names)

- [ ] **Step 3: Done**
