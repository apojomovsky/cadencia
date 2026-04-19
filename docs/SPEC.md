# Cadencia: v1 Implementation Spec

> **For AI agents**: Read `AGENTS.md` at the repo root before reading this file.
> This spec is the source of truth for what to build. If code and spec disagree, one is wrong.
> Never silently resolve that disagreement in favor of the code.

---

## 0. How to Use This Document

This is the complete implementation brief for Cadencia v1. It contains every product,
architecture, schema, and convention decision made during the design phase. It contains no code.

**Agents**: Pull the section(s) relevant to your task into context. You do not need to load the
whole document for every task, but you must load sections 1 and 8 (vision and conventions) before
starting anything. Always update this document if your implementation differs from what is
specified here.

**Humans**: If you want to change something in the implementation, change it here first. The doc
is the decision record. A change that is not in the doc is a change that future agents (and
future you) will not know about.

**Appendix B** (Decision Log) records every non-obvious choice with its rationale. Before
reversing or "improving" a design choice, check if it is recorded there and read why it was made.

---

## 1. Vision and Non-Goals

### 1.1 What this is

A self-hosted, single-user people management journal for an engineering manager. It stores
structured notes about direct reports and answers natural-language questions about the team via
an MCP server. It also provides a lightweight web UI for browsing and editing.

The defining property of this tool: it is the single, calm, queryable surface for everything the
manager needs to know about their team. It must survive the organizational chaos of quarterly
spreadsheet churn, be operable under ADHD conditions, and be portable (follows the manager if
they change companies).

### 1.2 Who it's for

Currently: one manager (the author), running entirely locally on their laptop.

Architecture is designed to not preclude multi-user deployment later (every record has an
`owner_id` column even though it is always the same value in v1), but multi-user features are
explicitly out of scope.

The code will eventually be open-sourced. Each manager runs their own instance with their own
private database. Code is shared; data never is.

### 1.3 Goals for v1

1. Capture observations about direct reports quickly (via MCP natural language, under 10 seconds).
2. Answer the Monday-morning questions: who is allocated where, who is stale, what is open.
3. Log 1:1 meetings with notes and action items.
4. Surface stale data without being asked (last allocation confirmation, last 1:1 date).
5. Back up the database automatically to personal Google Drive once per day.
6. Run entirely from `docker compose up` with no external dependencies beyond Docker.

### 1.4 Explicit non-goals for v1

These are hard stops. Do not implement any of the following, even if they seem like natural
extensions. They are explicitly deferred:

- Personal/health data storage (deferred: legal/GDPR review needed first)
- Scorecard spreadsheet import (deferred: schema for it comes after using the tool manually)
- Attrition signals as a separate entity (deferred: use observation tags instead in v1)
- Multi-user support (deferred: single-user only)
- Public internet exposure (Tailscale-only access is the security model)
- Mobile app or PWA (web UI on phone via Tailscale is sufficient)
- Calendar integration (deferred)
- Email/Slack notifications or reminders (deferred)
- Charts, dashboards, or analytics views (deferred: plain data is enough for v1)
- Automatic allocation sync from company spreadsheets (deferred to v3+)
- Authentication beyond Tailscale (no JWT, no OAuth, no sessions in v1)
- Quarterly scorecard goals or career aspiration tracking (deferred to v2)
- Encryption at the application layer (rely on full-disk encryption of host; revisit when
  personal data is added)

### 1.5 ADHD-aware design principles

These principles are non-negotiable and must inform every implementation decision:

1. **One inbox, one source of truth.** If the user ever has to ask "is the latest info here or
   somewhere else," the system has failed.
2. **Capture must be frictionless.** Logging an observation must take under 10 seconds via MCP.
   No required fields beyond person name.
3. **The system surfaces what is stale.** The user must not have to remember what needs
   updating. Stale-data indicators appear unprompted.
4. **Reading must be calm.** The person detail page shows five sections, in a fixed order, and
   nothing else.
5. **No required fields beyond name.** Partial data is always accepted. The system never blocks
   capture because a related field is missing.
6. **Decisions have reasons.** When structured data is updated (allocation, role, seniority),
   an optional `notes` field allows the reason to be attached. Future-you will not remember why.

---

## 2. Architecture Overview

### 2.1 Container topology

```
+---------------------------docker-compose---------------------------+
|                                                                    |
|  +-------------+     internal     +-------------+                 |
|  |     mcp     | <--- network ---> |     app     |                |
|  | (MCP server)|                  | (FastAPI +  |                 |
|  | HTTP/SSE    |                  |  HTMX + DB) |                 |
|  | port 8081   |                  | port 8080   |                 |
|  +-------------+                  +------+------+                 |
|                                          |                         |
|                                    named volume                    |
|                                    /data/em.db                     |
|                                          |                         |
|                                   +------+------+                  |
|                                   |   backup    |                  |
|                                   | (cron, once |                  |
|                                   |  daily)     |                  |
|                                   +------+------+                  |
|                                          |                         |
+------------------------------------------|-----------------------+
                                           |
                              rclone --> personal Google Drive
```

Three services. No service is exposed to the public internet. The host machine exposes:
- `localhost:8080` for the web UI (or bound to Tailscale interface for phone access)
- `localhost:8081` for the MCP server (Claude Desktop connects here)

### 2.2 Data flow

**Capture path (MCP):**
User speaks to Claude -> Claude calls MCP tool -> MCP server calls service function ->
service function writes to SQLite -> response back up the chain.

**Query path (MCP):**
User asks question -> Claude calls read MCP tool -> service function queries SQLite ->
structured response -> Claude synthesizes natural language answer.

**Browse/edit path (Web UI):**
User opens browser -> FastAPI serves HTMX template -> HTMX calls API endpoints ->
same service functions as MCP path -> HTML fragments returned and swapped in.

**Backup path:**
backup container wakes at 03:00 -> `sqlite3 .backup` to temp file -> gzip -> rclone upload ->
retention applied -> status written to shared volume sentinel file -> app reads sentinel on
next request -> backup status shown in UI.

### 2.3 Deployment model

- Runs on the user's laptop via `docker compose up`.
- SQLite data volume persists between container restarts.
- Web UI accessed at `http://localhost:8080` (or Tailscale IP for other devices).
- MCP server accessed at `http://localhost:8081/sse` configured in Claude Desktop's MCP config.
- No reverse proxy, no TLS, no external auth in v1. Tailscale provides network-level access
  control when accessed from other devices.
- The home server is a future backup target (via `dolt push` or a second rclone remote).
  Nothing in v1 should prevent adding it later. See section 7.6.

### 2.4 Repository layout

```
cadencia/
  AGENTS.md              # agent meta-guidance (you are here)
  docker-compose.yml     # base compose file
  docker-compose.dev.yml # dev overlay (bind mounts for hot reload, exposed debug ports)
  .env.example           # documents required env vars (committed)
  .env                   # actual secrets (gitignored)
  .dockerignore
  .gitignore
  README.md              # setup instructions for humans
  docs/
    SPEC.md              # this file
    decisions/           # ADRs for major decisions (short markdown files)
  app/
    Dockerfile           # multi-stage, non-root
    pyproject.toml
    src/
      cadencia/
        api/             # FastAPI route handlers (thin, delegate to services)
        models/          # Pydantic models for API and MCP schemas
        services/        # business logic (the only layer that touches the DB)
        web/             # Jinja2 templates and static files
        db/              # SQLAlchemy Core setup, connection, migration runner
    tests/
  mcp/
    Dockerfile
    pyproject.toml
    src/
      cadencia_mcp/
        server.py        # MCP server, imports from cadencia.services via HTTP or direct
    tests/
  dolt/                  # misnamed legacy: actually just SQL init files for SQLite
    init/
      001_initial_schema.sql
      002_seed_data.sql  # optional dev seed
  scripts/
    bootstrap.sh         # first-time setup (rclone auth, volume init)
    restore.sh           # restore procedure from Google Drive backup
```

Note on the `dolt/` directory name: it was named before the stack switched from Dolt to SQLite.
Rename to `db/` in implementation if preferred, but keep the init SQL file convention.

---

## 3. Data Model

### 3.1 The five tables

All tables include `owner_id TEXT NOT NULL DEFAULT 'default'` as a placeholder for future
multi-user support. All writes in v1 set this to the value of the `OWNER_ID` env var (defaults
to `'default'`). This column is indexed but never filtered in v1 queries (all data belongs to
the same owner).

```sql
-- People: one row per direct report
CREATE TABLE people (
  id          TEXT PRIMARY KEY,          -- UUID, generated on insert
  owner_id    TEXT NOT NULL DEFAULT 'default',
  name        TEXT NOT NULL,
  role        TEXT,                      -- e.g. "Senior Engineer", "Tech Lead"
  seniority   TEXT,                      -- P1 / P2 / P3 (company band labels)
  start_date  TEXT,                      -- ISO 8601 date, nullable
  status      TEXT NOT NULL DEFAULT 'active', -- active / leaving / left
  created_at  TEXT NOT NULL,             -- ISO 8601 datetime
  updated_at  TEXT NOT NULL
);

-- Observations: append-only notes about a person
CREATE TABLE observations (
  id          TEXT PRIMARY KEY,
  owner_id    TEXT NOT NULL DEFAULT 'default',
  person_id   TEXT NOT NULL REFERENCES people(id),
  observed_at TEXT NOT NULL,             -- ISO 8601 datetime (when it happened)
  created_at  TEXT NOT NULL,             -- ISO 8601 datetime (when logged)
  text        TEXT NOT NULL,             -- freeform markdown
  tags        TEXT NOT NULL DEFAULT '[]', -- JSON array of strings
  source      TEXT NOT NULL DEFAULT 'manual', -- manual / one_on_one / mcp / imported
  sensitivity TEXT NOT NULL DEFAULT 'normal'  -- normal / personal / confidential
                                         -- personal and confidential excluded from default
                                         -- queries; must be explicitly requested
);

-- One-on-ones: scheduled or completed 1:1 meetings
CREATE TABLE one_on_ones (
  id              TEXT PRIMARY KEY,
  owner_id        TEXT NOT NULL DEFAULT 'default',
  person_id       TEXT NOT NULL REFERENCES people(id),
  scheduled_date  TEXT NOT NULL,         -- ISO 8601 date
  completed       INTEGER NOT NULL DEFAULT 0, -- 0 = planned, 1 = completed
  notes           TEXT,                  -- freeform markdown, filled after meeting
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

-- Action items: tasks arising from 1:1s or captured ad hoc
CREATE TABLE action_items (
  id                  TEXT PRIMARY KEY,
  owner_id            TEXT NOT NULL DEFAULT 'default',
  person_id           TEXT NOT NULL REFERENCES people(id),
  source_one_on_one_id TEXT REFERENCES one_on_ones(id), -- nullable if captured ad hoc
  text                TEXT NOT NULL,
  owner_role          TEXT NOT NULL DEFAULT 'manager',  -- manager / report
  due_date            TEXT,                             -- ISO 8601 date, nullable
  status              TEXT NOT NULL DEFAULT 'open',     -- open / done / dropped
  created_at          TEXT NOT NULL,
  completed_at        TEXT                              -- nullable
);

-- Allocations: who is working on what, and at what commercial rate
CREATE TABLE allocations (
  id                   TEXT PRIMARY KEY,
  owner_id             TEXT NOT NULL DEFAULT 'default',
  person_id            TEXT NOT NULL REFERENCES people(id),
  type                 TEXT NOT NULL,       -- client / internal / bench
  client_or_project    TEXT,               -- nullable for bench
  percent              INTEGER,            -- 0-100, nullable if unknown
  rate_band            TEXT,              -- P1 / P2 / P3 or null
  start_date           TEXT NOT NULL,      -- ISO 8601 date
  end_date             TEXT,              -- nullable = current allocation
  last_confirmed_date  TEXT NOT NULL,      -- ISO 8601 date, updated manually
  notes                TEXT,
  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL
);

-- Activities: elective badge roles held in parallel to allocations
-- e.g. trainer, tech_mentor, operations_owner.  A person may hold multiple at once.
CREATE TABLE activities (
  id          TEXT PRIMARY KEY,
  owner_id    TEXT NOT NULL DEFAULT 'default',
  person_id   TEXT NOT NULL REFERENCES people(id),
  role        TEXT NOT NULL,    -- trainer / tech_mentor / coach / operations_owner /
                                --   operations_lead / community_rep / team_manager / account_manager
  power       TEXT,             -- power band: P1 / P2 / P3 / P4, nullable
  started_on  TEXT NOT NULL,    -- ISO 8601 date
  ended_on    TEXT,             -- nullable = currently active
  notes       TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
```

### 3.2 Naming and typing conventions

- All primary keys are UUIDs stored as TEXT. Generate with `uuid.uuid4()` in Python.
- All datetimes are ISO 8601 strings in UTC, stored as TEXT. Never store Unix timestamps.
- All dates are ISO 8601 strings (YYYY-MM-DD), stored as TEXT.
- Tags are JSON arrays stored as TEXT (SQLite has no array type). Always read/write via
  `json.loads` / `json.dumps`. Default is `'[]'`.
- Boolean-like fields use INTEGER (0/1). SQLite has no native boolean.
- All enum-like fields (status, type, source, sensitivity, seniority, owner_role) are TEXT
  constrained by CHECK constraints in the schema and validated in the service layer.
- Foreign keys are enabled via `PRAGMA foreign_keys = ON` on every connection.

### 3.3 Migration approach

Migrations are plain SQL files in `dolt/init/` (or `db/init/`), numbered sequentially:
`001_initial_schema.sql`, `002_add_something.sql`, etc.

A simple migration runner in `app/src/cadencia/db/migrations.py` tracks applied migrations
in a `_migrations` table and applies unapplied ones on app startup. The runner must be
idempotent: running it twice produces the same result as running it once.

Do not use Alembic. See AGENTS.md for the rationale.

### 3.4 Out of scope for v1 (tables we are NOT creating)

- `attrition_signals`: Use `observations` with `tags: ["attrition-risk"]` instead. The signals
  entity is v2 when we know what fields it actually needs.
- `scorecard_entries`: Deferred until the import flow is designed (v2).
- `career_aspirations`: Freeform for now via observations; structured later.
- `personal_context`: Explicitly deferred pending GDPR/legal review.
- `users` / `managers`: No multi-user in v1. `owner_id` is a placeholder, not a FK.

---

## 4. Service Layer

### 4.1 Design contract

`app/src/cadencia/services/` contains the only code that reads from or writes to the database.
No other module imports from `db/` directly. This is enforced by convention, not by the
language. Agents: if you find yourself writing a DB query outside of `services/`, stop.

Services are async Python functions. They accept typed Pydantic models as input and return typed
Pydantic models as output. They raise typed exceptions (defined in
`cadencia/services/exceptions.py`) which the API and MCP layers catch and translate into
appropriate error responses.

### 4.2 Service modules

```
services/
  people.py       # CRUD for people
  observations.py # create, query observations
  one_on_ones.py  # create, complete, query 1:1s
  action_items.py # create, complete, query action items
  allocations.py  # create, update (end-date current, start new), query
  queries.py      # cross-table derived queries (whats_stale, prepare_one_on_one, etc.)
  exceptions.py   # NotFoundError, ValidationError, ConflictError
```

### 4.3 Key service functions (interface-level)

The following are the service functions that must exist at v1 completion. Signatures are
illustrative; implementation may add keyword arguments but must not remove these parameters.

```python
# people.py
async def list_people(db, status: str = "active") -> list[PersonSummary]
async def get_person(db, person_id: str) -> PersonDetail
async def resolve_person(db, query: str) -> list[PersonSummary]  # name search, for MCP
async def create_person(db, data: CreatePersonInput) -> PersonDetail
async def update_person(db, person_id: str, data: UpdatePersonInput) -> PersonDetail

# observations.py
async def add_observation(db, data: AddObservationInput) -> Observation
async def list_observations(db, person_id: str, since: str | None, tags: list[str],
                            include_sensitive: bool = False) -> list[Observation]

# one_on_ones.py
async def log_one_on_one(db, data: LogOneOnOneInput) -> OneOnOne
async def get_upcoming_one_on_ones(db, within_days: int = 7) -> list[OneOnOnePreview]

# action_items.py
async def get_open_action_items(db, person_id: str | None = None) -> list[ActionItem]
async def complete_action_item(db, action_item_id: str,
                               completion_notes: str | None = None) -> ActionItem

# allocations.py
async def get_current_allocation(db, person_id: str) -> Allocation | None
async def update_allocation(db, data: UpdateAllocationInput) -> Allocation

# queries.py
async def whats_stale(db, allocation_threshold_days: int = 45,
                      one_on_one_threshold_days: int = 14) -> StalenessReport
async def prepare_one_on_one(db, person_id: str) -> OneOnOnePrep
async def get_person_overview(db, person_id: str,
                              include_sensitive: bool = False) -> PersonOverview
```

### 4.4 Audit and logging requirements

Every service function that writes to the database must emit a structured log line to stdout.
Format (Python `logging` module, level INFO):

```
{"event": "write", "table": "observations", "operation": "insert",
 "record_id": "uuid", "person_id": "uuid", "source": "mcp|api",
 "ts": "2026-04-15T14:32:00Z"}
```

The `source` field is passed in from the calling layer (API routes set `source="api"`, MCP tools
set `source="mcp"`). Do not infer it inside the service.

---

## 5. MCP Server

### 5.1 Transport

HTTP/SSE transport. The MCP server runs in its own container on port 8081. Claude Desktop
connects to `http://localhost:8081/sse`.

The MCP server imports service functions from the `cadencia` package (shared via docker volume
mount in dev, or by installing the package from the app wheel in prod). It does not call the
FastAPI HTTP API. Both the MCP server and the FastAPI app share the same service layer code.

The SQLite database file is mounted at `/data/em.db` in both the `app` and `mcp` containers.
Both containers open the same SQLite file. SQLite WAL mode is enabled to allow concurrent
readers. Only one writer at a time: SQLite's write locking handles this; it is acceptable for
single-user load.

### 5.2 The nine MCP tools

Tool names, descriptions, and schemas are the public API. Do not change them without updating
this section first.

---

**`list_people`**

Lists all active direct reports with summary information.

Input:
```json
{
  "status": {"type": "string", "enum": ["active", "leaving", "left", "all"],
             "default": "active", "description": "Filter by employment status."}
}
```

Output: array of PersonSummary objects:
```json
[{
  "id": "uuid",
  "name": "string",
  "role": "string | null",
  "seniority": "string | null",
  "current_allocation_type": "string | null",
  "last_one_on_one_date": "string | null",
  "open_action_items_count": "integer"
}]
```

---

**`get_person`**

Returns the full current overview for one person: allocation, recent observations, open action
items, last 1:1 date, next scheduled 1:1 if any.

Input:
```json
{
  "person": {"type": "string",
             "description": "Person name or ID. Partial names are accepted; if ambiguous, returns an error listing candidates."}
}
```

Output: PersonOverview (see section 4.3, `get_person_overview`). Excludes observations with
`sensitivity != "normal"` unless `include_sensitive` is explicitly true (not exposed in v1).

---

**`add_observation`**

Records a new observation about a person. This is the primary capture tool.

Input:
```json
{
  "person": {"type": "string", "description": "Person name or ID."},
  "text": {"type": "string", "description": "The observation, in markdown. Can be brief or detailed."},
  "tags": {"type": "array", "items": {"type": "string"}, "default": [],
           "description": "Optional tags. Common tags: attrition-risk, growth, feedback-given, praise, concern, career, allocation."},
  "observed_at": {"type": "string",
                  "description": "ISO 8601 datetime or date when this observation occurred. Defaults to now if omitted."}
}
```

Output:
```json
{"id": "uuid", "person_id": "uuid", "person_name": "string", "observed_at": "string"}
```

---

**`log_one_on_one`**

Records a completed 1:1 meeting with notes and optional action items.

Input:
```json
{
  "person": {"type": "string"},
  "date": {"type": "string", "description": "ISO 8601 date of the meeting."},
  "notes": {"type": "string", "description": "Meeting notes, markdown."},
  "action_items": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "text": {"type": "string"},
        "owner": {"type": "string", "enum": ["manager", "report"], "default": "manager"},
        "due_date": {"type": "string", "description": "ISO 8601 date, optional."}
      },
      "required": ["text"]
    },
    "default": []
  }
}
```

Output:
```json
{"one_on_one_id": "uuid", "person_id": "uuid", "person_name": "string",
 "action_items_created": "integer"}
```

---

**`update_allocation`**

Updates the current allocation for a person. Ends the previous allocation (sets `end_date`) and
creates a new one. To mark a person as bench, use `type: "bench"` with no client.

Input:
```json
{
  "person": {"type": "string"},
  "type": {"type": "string", "enum": ["client", "internal", "bench"]},
  "client_or_project": {"type": "string", "description": "Required when type is client or internal. Omit for bench."},
  "percent": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Allocation percentage, optional."},
  "rate_band": {"type": "string", "enum": ["P1", "P2", "P3"], "description": "Billing rate band, optional."},
  "start_date": {"type": "string", "description": "ISO 8601 date. Defaults to today."},
  "notes": {"type": "string", "description": "Reason for the change, optional but encouraged."}
}
```

Output:
```json
{"allocation_id": "uuid", "person_id": "uuid", "person_name": "string",
 "previous_allocation_ended": "boolean"}
```

---

**`complete_action_item`**

Marks an action item as done.

Input:
```json
{
  "action_item_id": {"type": "string", "description": "UUID of the action item."},
  "completion_notes": {"type": "string", "description": "Optional notes on how it was resolved."}
}
```

Output:
```json
{"action_item_id": "uuid", "person_name": "string", "text": "string", "completed_at": "string"}
```

---

**`whats_stale`**

Returns a report of what needs attention: people whose allocation has not been confirmed
recently, and people due for a 1:1. This is the Monday-morning entry point tool.

Input:
```json
{
  "allocation_threshold_days": {"type": "integer", "default": 45,
    "description": "Flag allocation as stale if last_confirmed_date is older than this."},
  "one_on_one_threshold_days": {"type": "integer", "default": 14,
    "description": "Flag a person as overdue for 1:1 if last 1:1 was more than this many days ago."}
}
```

Output:
```json
{
  "stale_allocations": [{"person_id": "uuid", "person_name": "string",
                          "days_since_confirmed": "integer",
                          "current_allocation_type": "string | null"}],
  "overdue_one_on_ones": [{"person_id": "uuid", "person_name": "string",
                            "days_since_last_one_on_one": "integer | null",
                            "next_scheduled": "string | null"}],
  "overdue_action_items": [{"action_item_id": "uuid", "person_name": "string",
                             "text": "string", "due_date": "string",
                             "days_overdue": "integer"}]
}
```

---

**`add_activity`**

Record that a person has taken on an elective badge activity. Activities run in parallel to
client allocations; a person may hold multiple at once.

Input:
```json
{
  "person": {"type": "string", "description": "Name (partial match ok) or UUID."},
  "role": {"type": "string", "description": "One of: trainer, tech_mentor, coach, operations_owner, operations_lead, community_rep, team_manager, account_manager."},
  "power": {"type": "string | null", "description": "Power band: P1–P4. Optional."},
  "started_on": {"type": "string | null", "description": "ISO 8601 date. Defaults to today."},
  "notes": {"type": "string | null", "description": "Optional free-form context."}
}
```

Output: the created `Activity` object.

---

**`end_activity`**

Mark an elective badge activity as ended. Ends the most recent open activity with the given role.

Input:
```json
{
  "person": {"type": "string", "description": "Name (partial match ok) or UUID."},
  "role": {"type": "string", "description": "The activity role to end."},
  "ended_on": {"type": "string | null", "description": "ISO 8601 date. Defaults to today."}
}
```

Output: the updated `Activity` object with `ended_on` set.

---

### 5.3 Error responses

All MCP tool errors return a structured error:
```json
{"error": "NotFound | ValidationError | Ambiguous | Internal",
 "message": "human-readable string",
 "candidates": ["list of names if Ambiguous"]}
```

`Ambiguous` is returned when a name query matches more than one person. The caller should
call the tool again with a more specific name or the person's ID.

### 5.4 Sensitivity hook

Observations with `sensitivity != "normal"` are excluded from all MCP read tools by default.
The v1 MCP surface has no way to request sensitive observations. This is intentional.
The hook exists in the service layer (`include_sensitive=False` parameter). Do not expose it
via MCP in v1.

---

## 6. Web UI

### 6.1 Pages

Two pages in v1:
1. **People list** (`/`): overview of all active reports
2. **Person detail** (`/people/{person_id}`): the five-section view for one person

No other pages in v1. Navigation is: list -> detail -> back to list. That's it.

### 6.2 People list page (`/`)

```
Cadencia                                  [last backup: 2 hours ago]
-----------------------------------------------------------------
People                                               [+ Add person]

  Alice Nguyen          Senior Engineer  P2  |  ClientCo (60%)  |  1:1 in 2 days  |  2 open
  Bob Ferreira          Tech Lead        P3  |  Internal: Arch   |  1:1 OVERDUE    |  0 open
  Carla Méndez          Engineer         P1  |  BENCH            |  1:1 in 5 days  |  1 open
  Dimitri Karov         Senior Engineer  P2  |  alloc: STALE 52d |  1:1 in 1 day   |  0 open
```

Each row is clickable, links to person detail. Indicators:
- `1:1 OVERDUE`: last 1:1 was more than 14 days ago (threshold configurable via env).
- `alloc: STALE Nd`: `last_confirmed_date` was more than 45 days ago.
- `N open`: count of open action items.

The backup status line (`last backup: 2 hours ago`) appears in the top-right of every page.
Turns to `[backup: OVERDUE]` if no successful backup in more than 25 hours.

### 6.3 Person detail page (`/people/{person_id}`)

Five sections, in fixed order, no reordering:

```
[<- People]  Alice Nguyen  |  Senior Engineer  |  P2  |  Since 2023-04-01

-----------------------------------------------------------------
RIGHT NOW
  ClientCo  |  60%  |  P2 rate  |  Start: 2026-01-15  |  confirmed 3 days ago

-----------------------------------------------------------------
OPEN WITH HER
  Next 1:1: 2026-04-17 (in 2 days)
  [x] Action (manager): Review her architecture proposal     due Apr 20
  [ ] Action (her):     Share updated tech radar preferences

-----------------------------------------------------------------
RECENT SIGNAL  (last 90 days)
  2026-04-10  She's frustrated with lack of architectural ownership on perception stack.
              Mentioned talking to a recruiter casually.   [attrition-risk] [career]
  2026-04-03  Good energy in the planning session. Proactively helped junior pair.  [growth]
  2026-03-28  One-on-one notes: see meeting log.           [one_on_one]

-----------------------------------------------------------------
ALLOCATION HISTORY   [collapsed by default, expand to view]

-----------------------------------------------------------------
FULL LOG             [collapsed by default, expand to view]
```

The top two sections (RIGHT NOW, OPEN WITH HER) must be visible without scrolling on a 1080p
display. The bottom two sections are collapsed by default; HTMX loads them on expand.

### 6.4 HTMX patterns

- The list page is server-rendered HTML on initial load.
- Row-level action (complete action item, confirm allocation) sends HTMX requests and swaps
  only the relevant fragment. No full-page reload.
- Collapsed sections (ALLOCATION HISTORY, FULL LOG) are loaded via HTMX `hx-get` on expand.
  They are not included in the initial page render.
- There is no client-side state management. All state lives in the database. HTMX + server
  rendering is sufficient.
- Do not add JavaScript beyond what HTMX loads. No bundler, no npm.

### 6.5 Out of scope for v1 UI

- Charts, graphs, timelines, heatmaps.
- Inline editing of observation text (add-only in v1; editing is out of scope).
- Search or filter on the list page.
- Multi-column sort on the list page.
- Dark mode toggle (use system preference via CSS `prefers-color-scheme` only).
- Add person form (create person via MCP in v1; the form is v2).

---

## 7. Backup System

### 7.1 Container design

The `backup` container is a minimal Alpine-based image with `sqlite3`, `rclone`, and a shell
script. It runs a loop that checks the time and fires the backup at 03:00 local time (configurable
via `BACKUP_HOUR` env var).

The container mounts:
- The same named volume as `app` at `/data/em.db` (read-only for safety).
- A sentinel directory at `/backup-status/` (read-write, shared with `app`).
- The rclone config at `/rclone/rclone.conf` (read-write; rclone refreshes OAuth tokens).

### 7.2 Backup procedure

Never copy the SQLite file with `cp` or `rsync` while it may be in WAL mode. Always use:
```bash
sqlite3 /data/em.db ".backup /tmp/em.db"
```

This produces a consistent snapshot even under concurrent reads.

After backup, bundle the database and the context directory into a single archive:
```bash
tar -czf /tmp/cadencia-${TIMESTAMP}.tar.gz -C /tmp em.db -C /data context
```

The archive contains `em.db` at the root and a `context/` directory. If `/data/context` does not exist or is empty, it is omitted without error.

Final artifact: `cadencia-YYYYMMDD-HHMMSS.tar.gz`.

### 7.3 rclone configuration

Remote name: configured via `RCLONE_REMOTE` env var (default: `gdrive`).
Destination path: configured via `BACKUP_PATH` env var (default: `cadencia-backups`).

Full upload command:
```bash
rclone copy /tmp/cadencia-${TIMESTAMP}.tar.gz "${RCLONE_REMOTE}:${BACKUP_PATH}/"
```

**First-time setup (manual, one-time)**: Run `rclone config` on the host to create the Google
Drive remote. Copy the resulting `~/.config/rclone/rclone.conf` to `./secrets/rclone.conf` in
the project directory. The backup container mounts it. Document this in README.md setup section.

To add a corporate Google Drive remote later: add a second remote to the same `rclone.conf` and
extend the backup script to also push to `${RCLONE_REMOTE_CORP}:${BACKUP_PATH_CORP}/`. This is
a config-only change.

### 7.4 Retention policy

Applied after each upload using `rclone delete`:
- Keep all backups from the last 30 days.
- Keep one backup per week from 31-365 days ago (the most recent one of each week).
- Delete anything older than 365 days.

Implement retention as a shell function in the backup script. Do not use a third-party tool.

### 7.5 Failure detection and surfacing

After each run, the backup script writes a JSON sentinel file:
```bash
echo '{"success": true, "ts": "2026-04-15T03:01:23Z", "file": "cadencia-....tar.gz"}' \
  > /backup-status/last.json
```

On failure, `"success": false` with an `"error"` field.

The FastAPI app reads `/backup-status/last.json` on startup and on each request to `/health`.
The person list page template includes the backup status in the top-right. Age is computed
against the current time at render.

### 7.6 Restore procedure

Documented in README.md. Summary:
1. `docker compose down`
2. `rclone ls gdrive:cadencia-backups/` to list available backups.
3. `rclone copy gdrive:cadencia-backups/cadencia-TIMESTAMP.tar.gz /tmp/`
4. Extract database: `tar -xzf /tmp/cadencia-TIMESTAMP.tar.gz -C /tmp em.db`
5. `docker volume create cadencia_data` (if not exists)
6. Copy database into volume: `docker run --rm -v cadencia_data:/data -v /tmp:/tmp alpine cp /tmp/em.db /data/em.db`
7. If the archive contains a `context/` directory, extract and copy it too: `tar -xzf ... -C /tmp context && docker run --rm -v cadencia_data:/data -v /tmp:/tmp alpine sh -c "cp -r /tmp/context /data/context"`
8. `docker compose up`

The `scripts/restore.sh` script implements these steps with prompts for confirmation. It also handles the legacy `.db.gz` format (database-only restore, no context) for backups created before this change.

---

## 8. Docker and Operational Conventions

### 8.1 Container topology

Three containers, as described in section 2.1. Container names in compose: `app`, `mcp`, `backup`.
Internal network: `cadencia_net` (bridge). Only `app` and `mcp` are on it.

Published ports (dev): `app:8080`, `mcp:8081`. In production mode (home server), bind to
Tailscale interface instead of `0.0.0.0`.

### 8.2 Dockerfile conventions

Apply to all Dockerfiles in this project:

- **Multi-stage builds**: `builder` stage installs dependencies; `runtime` stage copies only the
  installed packages and app code. Python images: `python:3.12-slim-bookworm` for runtime.
- **Pinned versions**: No `:latest` tags. Pin the full version including patch: `python:3.12.3-slim-bookworm`.
- **Non-root user**: Every runtime stage creates and switches to an `app` user:
  ```dockerfile
  RUN useradd --create-home --shell /bin/bash app
  USER app
  ```
- **WORKDIR**: Set to `/app` for app/mcp containers, `/backup` for the backup container.
- **No secrets in image**: All credentials come from env vars or mounted files at runtime.

### 8.3 Compose structure

`docker-compose.yml`: production-ready configuration. No bind mounts of source code.
Image tags are explicit. Healthchecks defined.

`docker-compose.dev.yml`: overlay for development.
```yaml
# Adds hot reload and debug port exposure
services:
  app:
    volumes:
      - ./app/src:/app/src  # hot reload
    command: uvicorn cadencia.main:app --reload --host 0.0.0.0 --port 8080
  mcp:
    volumes:
      - ./mcp/src:/app/src
      - ./app/src:/cadencia_src  # shared service code
```

Run in dev: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`
Run in prod: `docker compose up`

### 8.4 Environment variables

All required vars documented in `.env.example`. Never committed in `.env`.

```bash
# .env.example
OWNER_ID=default                   # logical owner for multi-user future
BACKUP_REMOTE=gdrive               # rclone remote name
BACKUP_PATH=cadencia-backups     # path within remote
BACKUP_HOUR=3                      # hour (local time) to run daily backup
ALLOCATION_STALE_DAYS=45           # threshold for stale allocation warning
ONE_ON_ONE_STALE_DAYS=14           # threshold for overdue 1:1 warning
```

### 8.5 Healthchecks

All three services must have healthchecks defined in `docker-compose.yml`:

- `app`: `GET http://localhost:8080/health` returns 200.
- `mcp`: `GET http://localhost:8081/health` returns 200.
- `backup`: `test -f /backup-status/last.json` (file exists after first run).

The `/health` endpoint on the app also returns the backup sentinel status, so it is a useful
indicator of overall system health.

### 8.6 Logging conventions

- All containers log to stdout/stderr. Docker captures and aggregates.
- Log format: structured JSON (using Python's `logging` with a JSON formatter). Do not use
  `print()` for application logs.
- Log level: INFO in production, DEBUG in dev (set via `LOG_LEVEL` env var).
- Every HTTP request is logged by FastAPI's built-in request logging middleware (no custom
  middleware needed).
- Every write to the database emits one INFO log per section 4.4.

---

## 9. Code Conventions

### 9.1 Python version and tooling

- Python 3.12.
- `ruff` for linting and formatting (replaces black + flake8 + isort). Config in `pyproject.toml`.
- `mypy` for type checking. Strict mode (`--strict`) enabled.
- `pytest` with `pytest-asyncio` for tests.
- `uv` preferred over `pip` for package management inside containers.

### 9.2 Module structure within `cadencia`

```
cadencia/
  __init__.py
  main.py           # FastAPI app factory
  config.py         # Pydantic Settings (reads .env)
  api/
    __init__.py
    people.py       # /people routes
    one_on_ones.py  # /one_on_ones routes
    action_items.py # /action_items routes
    allocations.py  # /allocations routes
    health.py       # /health route
  models/
    __init__.py
    people.py       # Pydantic in/out models for people
    observations.py
    one_on_ones.py
    action_items.py
    allocations.py
    queries.py      # StalenessReport, OneOnOnePrep, PersonOverview
  services/         # (see section 4)
  web/
    templates/      # Jinja2 .html files
    static/         # CSS, htmx.min.js (vendored, not CDN)
  db/
    __init__.py
    connection.py   # SQLAlchemy Core engine and session
    migrations.py   # migration runner
```

### 9.3 Naming conventions

- Python: snake_case for functions, variables, modules; PascalCase for classes.
- SQL table and column names: lowercase_snake_case.
- MCP tool names: lowercase_snake_case.
- FastAPI route paths: lowercase, hyphens for multi-word segments (`/action-items`, not `/actionItems`).
- Docker container names: lowercase, no hyphens (`app`, `mcp`, `backup`).
- Environment variable names: SCREAMING_SNAKE_CASE.

### 9.4 Test expectations for v1

See AGENTS.md for the full testing philosophy. In brief:
- One happy-path test per service function.
- Use a real SQLite file (temp file in `tmp_path` pytest fixture). No mocks.
- API tests use FastAPI `TestClient`.
- MCP transport tests are skipped with `@pytest.mark.skip`.
- Target: all service functions covered, API routes smoke-tested. No coverage target beyond that.

### 9.5 Documentation expectations

- `README.md` at the repo root: setup instructions (docker, rclone auth, first run).
  Target audience: another manager setting up their own instance.
- `docs/SPEC.md`: this file, kept updated.
- `docs/decisions/`: short ADRs for major choices (SQLite over Dolt, HTMX over React, etc.).
  Format: Context, Decision, Consequences. Three paragraphs max each.
- No docstrings required on internal functions. Docstrings required on all public service
  functions (the ones listed in section 4.3) and all MCP tool handler functions.

---

## 10. Acceptance Criteria for v1

v1 is complete when all of the following are true:

1. **`docker compose up` produces a working system.** No manual steps beyond rclone auth (one-time
   setup) and populating `.env`.

2. **The Monday-morning workflow works end to end.**
   - Claude Desktop (or any MCP client) connects to the MCP server.
   - User can call `whats_stale` and get a meaningful response.
   - User can call `add_observation` and the observation persists across container restarts.
   - User can call `log_one_on_one` with action items and they appear in `get_person` output.

3. **All seven MCP tools are callable and return correct output.**
   Test each against a seeded database with at least 2 people and realistic data.

4. **Both web UI pages render and basic interactions work.**
   - People list shows all active people with indicators.
   - Person detail shows all five sections in order.
   - Completing an action item via HTMX updates the page without a full reload.
   - Collapsed sections load on expand.

5. **A backup runs, succeeds, and the result can be restored.**
   - Trigger the backup script manually (outside the 03:00 schedule).
   - Verify the file appears in Google Drive.
   - Follow the restore procedure and verify the restored database matches the original.

6. **The backup status indicator is visible and accurate.**
   - After a successful backup, the list page shows the timestamp.
   - Modify the sentinel to simulate a 26-hour-old backup; confirm the UI shows `OVERDUE`.

7. **All service function tests pass.**
   - `pytest app/tests/` passes with no failures and no skipped tests except the MCP transport
     integration test.

---

## 11. Roadmap (Informative, Not Implementation Scope)

### 11.1 v2 candidates (in rough priority order)

1. **Scorecard / goals tracking**: annual personal and professional goals, quarterly actionables.
   Schema: `scorecard_entries` table (see section 3.4). Import from the company's spreadsheet
   format. Reverse direction: AI suggests updates based on accumulated observations.

2. **Attrition signal entity**: first-class `attrition_signals` table with severity, mitigation
   plan, and status tracking. Spawn from observations tagged `attrition-risk`.

3. **Add person via web UI**: currently MCP-only in v1. A simple form on the list page.

4. **Career profile**: structured interests, aspirations, short/mid/long-term goals per person.
   Feed into `prepare_one_on_one` output.

5. **Home server sync**: `dolt push` or a second rclone remote for offsite backup beyond Drive.

### 11.2 v3+ ideas

- Automatic allocation sync from company spreadsheets (fragile; needs stable schema first).
- Personal/health context storage (pending GDPR/legal review; requires encryption at rest).
- Multi-user support (multiple managers, each with their own data partition).
- Mobile-optimized capture interface.
- Public internet exposure with real auth (Tailscale-only is fine until this is needed).
- Calendar integration for 1:1 scheduling.
- Weekly digest email/notification to self.
- Open-source release and documentation for other managers.

---

## Appendix A: Glossary

| Term | Meaning in this project |
|---|---|
| Direct report | A person on the manager's team; a row in the `people` table |
| Observation | An append-only note about a person; a row in `observations` |
| Allocation | A time-bounded assignment to a client, internal project, or bench |
| Bench | Status when a person is between client assignments (billable downtime) |
| Seniority / Band | Company compensation band: P1 (junior), P2 (mid), P3 (senior) |
| Stale | Allocation not confirmed, or 1:1 not held, within the configured threshold |
| MCP | Model Context Protocol; used to expose tools to AI clients like Claude Desktop |
| Service layer | The Python module layer that owns all database access |
| Sentinel file | `/backup-status/last.json`; communicates backup health between containers |
| Owner ID | `owner_id` column present in all tables; always `'default'` in v1; future-proofing for multi-user |

---

## Appendix B: Decision Log

**B.1 SQLite over Dolt**
SQLite was chosen over Dolt (git for SQL) because the primary requirement is simplicity and
operational lightness, not cell-level history or data branching. Dolt's differentiating features
(versioned data, `AS OF` queries, branch-per-experiment) are not needed for a single-user
journal. SQLite is a single file, zero-config, and universally supported. Dolt is valid if you
want the git-native history story; revisit if you need `AS OF` queries or multi-writer support.

**B.2 HTMX over React (or other SPA frameworks)**
HTMX was chosen to avoid a JavaScript build step and keep the stack minimal. The UI has two
pages with modest interactivity (fragment swaps, lazy section loading). This does not justify
the operational overhead of a bundler, node_modules, or a component framework. The trade-off is
a less rich client-side experience, which is acceptable given the use case (desktop browser,
occasional use). Revisit if the UI needs real-time updates, drag-and-drop, or complex client
state.

**B.3 Three containers over one**
Each container does one thing: the app serves the web UI and API, the MCP server handles AI
protocol, the backup container handles scheduling and rclone. This separation makes each
component independently restartable, testable, and replaceable. The cost is slightly more
docker-compose configuration. Worth it for clarity and the open-source-sharing story.

**B.4 Personal Google Drive over corporate Google Drive**
The data in this system constitutes manager notes about employees. Storing it on corporate
infrastructure changes its legal posture (potentially discoverable in employment disputes,
subject to company retention policies, accessible to IT admins). Personal Drive keeps it in
the manager's personal sphere. The architecture supports adding a corporate Drive remote later
as a config-only change (second rclone remote).

**B.5 Manual allocation entry over auto-sync**
The company tracks allocations in quarterly spreadsheets that change format unpredictably.
Auto-sync would require a parser that breaks on every format change. Manual entry is bounded
effort (30 minutes per quarter), forces the manager to consciously review changes, and builds
a clean historical record that the company spreadsheets do not provide. The `last_confirmed_date`
field and staleness indicator manage the "did I forget to update this" risk.

**B.6 Sensitivity field present but not exposed in MCP v1**
Personal and health-related observations require GDPR review before implementing systematic
storage. The `sensitivity` column is in the schema so that when v2 adds this feature, no
migration is needed. The `include_sensitive=False` default in service layer queries and the
absence of an `include_sensitive` parameter in MCP tools ensure this data is not accidentally
surfaced. Do not add it to the MCP surface without revisiting the legal/ethical section.
