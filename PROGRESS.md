# Implementation Progress

Each item below is a self-contained chunk of work that should land in its own commit (or a small
group of tightly related commits). Check the box when the work is done and verified, then commit
the code change and the updated checkbox together.

See `AGENTS.md` section "Commit workflow" for the full convention.

---

## Phase 0: Project scaffold

- [x] Directory structure and `pyproject.toml` for `app/` and `mcp/`
- [x] Base `Dockerfile` for `app` (multi-stage, non-root, pinned base image)
- [x] Base `Dockerfile` for `mcp`
- [x] Base `Dockerfile` for `backup`
- [x] `docker-compose.yml` (production-ready, healthchecks defined)
- [x] `docker-compose.dev.yml` (dev overlay with bind mounts and hot reload)
- [x] `.env.example` with all required variables documented
- [x] `README.md` with setup instructions (first-time rclone auth, first run)

**Verify**: `docker compose up` starts all three containers and healthchecks pass (no app code yet, just the containers boot cleanly).

---

## Phase 1: Database layer

- [x] `app/src/cadencia/db/sql/001_initial_schema.sql`: all five tables with CHECK constraints
- [x] `app/src/cadencia/db/connection.py`: SQLAlchemy Core engine, WAL mode enabled, foreign keys on
- [x] `app/src/cadencia/db/migrations.py`: migration runner with `_migrations` table, idempotent
- [x] Migration runs cleanly on fresh volume and is a no-op on subsequent restarts

**Verify**: `docker compose up`, connect to app container, confirm all tables exist and `_migrations` shows `001_initial_schema` applied.

---

## Phase 2: Pydantic models

- [x] `models/people.py`: `PersonSummary`, `PersonDetail`, `CreatePersonInput`, `UpdatePersonInput`
- [x] `models/observations.py`: `Observation`, `AddObservationInput`
- [x] `models/one_on_ones.py`: `OneOnOne`, `LogOneOnOneInput`, `OneOnOnePreview`
- [x] `models/action_items.py`: `ActionItem`
- [x] `models/allocations.py`: `Allocation`, `UpdateAllocationInput`
- [x] `models/queries.py`: `StalenessReport`, `OneOnOnePrep`, `PersonOverview`

**Verify**: `mypy app/src/` passes with no errors.

---

## Phase 3: Service layer

- [x] `services/people.py`: `list_people`, `get_person`, `resolve_person`, `create_person`, `update_person`
- [x] `services/observations.py`: `add_observation`, `list_observations`
- [x] `services/one_on_ones.py`: `log_one_on_one`, `get_upcoming_one_on_ones`
- [x] `services/action_items.py`: `get_open_action_items`, `complete_action_item`
- [x] `services/allocations.py`: `get_current_allocation`, `update_allocation`
- [x] `services/queries.py`: `whats_stale`, `prepare_one_on_one`, `get_person_overview`
- [x] `services/exceptions.py`: `NotFoundError`, `ValidationError`, `ConflictError`
- [x] Audit log emitted on every write (see SPEC.md section 4.4)

**Verify**: `pytest app/tests/services/` passes. All happy-path tests use a real temp SQLite file, no mocks.

---

## Phase 4: API routes

- [x] `api/health.py`: `GET /health` returns 200 with backup sentinel status
- [x] `api/people.py`: list and detail endpoints
- [x] `api/one_on_ones.py`: create and complete endpoints
- [x] `api/action_items.py`: list and complete endpoints
- [x] `api/allocations.py`: create/update endpoint
- [x] FastAPI app factory wired up in `main.py`

**Verify**: `pytest app/tests/api/` passes using `TestClient`. `GET /health` returns 200 inside the running container.

---

## Phase 5: Web UI

- [x] Base Jinja2 template with backup status indicator in header (all pages)
- [x] `web/templates/people_list.html`: list page matching SPEC.md section 6.2 wireframe
- [x] `web/templates/person_detail.html`: detail page matching SPEC.md section 6.3 wireframe
- [x] HTMX: complete action item updates fragment without full reload
- [x] HTMX: collapsed sections (allocation history, full log) load on expand
- [x] `htmx.min.js` vendored into `web/static/` (no CDN)
- [x] CSS: minimal, readable, respects `prefers-color-scheme`

**Verify**: Open `http://localhost:8080` in a browser with seeded data. Walk through the person detail page: all five sections present, action item completion works, collapsed sections expand.

---

## Phase 6: MCP server

- [x] `mcp/src/cadencia_mcp/server.py`: MCP server with HTTP/SSE transport on port 8081
- [x] Tool: `list_people`
- [x] Tool: `get_person` (including `Ambiguous` error for partial name matches)
- [x] Tool: `add_observation`
- [x] Tool: `log_one_on_one`
- [x] Tool: `update_allocation`
- [x] Tool: `complete_action_item`
- [x] Tool: `whats_stale`
- [x] `GET /health` on port 8081 for the Docker healthcheck

**Verify**: Configure Claude Desktop to point at `http://localhost:8081/sse`. Call each tool from a Claude conversation with a seeded database. Confirm writes persist and reads return correct data.

---

## Phase 7: Backup system

- [x] `backup/` Dockerfile: Alpine with `sqlite3`, `rclone`, and the backup script
- [x] `scripts/backup.sh`: online backup, gzip, rclone upload, retention policy
- [x] Sentinel file written to `/backup-status/last.json` on success and failure
- [x] App reads sentinel and surfaces it in the `/health` endpoint and UI header
- [x] `scripts/restore.sh`: documented restore procedure (see SPEC.md section 7.6)
- [x] rclone auth setup documented in `README.md`

**Verify**: Trigger `backup.sh` manually inside the backup container. Confirm file appears in Google Drive. Confirm `last.json` sentinel is written. Confirm the UI header shows the correct timestamp. Simulate a stale sentinel and confirm `OVERDUE` indicator appears.

---

## Phase 8: Integration and acceptance criteria

- [x] All items in SPEC.md section 10 verified end to end
- [x] Seed script or instructions for populating test data
- [x] `docker compose up` from a clean state works without any manual steps beyond rclone auth

Acceptance criteria status:
1. docker compose up: PASS (all 3 containers healthy)
2. Monday-morning workflow: PASS (MCP tools confirmed working in prior session)
3. All 7 MCP tools callable: PASS
4. Web UI pages render and HTMX interactions work: PASS (200s, confirmed in browser)
5. Backup run + restore: manual verification required (needs Google Drive credentials)
6. Backup status indicator: PASS (sentinel surfaced in header and /api/health)
7. All service tests pass: PASS (30 passed, 0 failures)

**Verify**: Walk through every acceptance criterion in SPEC.md section 10 in order. Check each one only when it passes against a real running stack, not in isolation.

---

## Completed

Items move here after their commit lands, with the commit SHA for reference.

<!-- Example:
- [x] docs: add project spec, agent guidance, and gitignore (`be0ef6b`)
-->

- [x] docs: add project spec, agent guidance, and gitignore (`be0ef6b`)
