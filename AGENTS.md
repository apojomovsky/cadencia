# Agent Implementation Guide

This file contains meta-guidance for any AI agent (Claude Code or otherwise) working on this codebase.
Read this before reading SPEC.md. These rules override any default agent preferences.

---

## What this project is

A personal people-management tool for a single engineering manager. It stores structured notes
about direct reports and exposes them via an MCP server (for AI-assisted queries and capture)
and a web UI (for browsing and editing). Everything runs locally via Docker Compose.

The full product spec is in `docs/SPEC.md`. Read it before implementing anything.

---

## Getting started (MCP setup for agents)

The repo root contains `.mcp.json` which points Claude Code at the EM Journal MCP server
(`http://localhost:8081/sse`). For the tools to work, the stack must be running:

```bash
docker compose up -d
```

That starts three containers: `app` (web UI + REST API on port 8080), `mcp` (MCP server on
port 8081), and `backup` (daily SQLite backup to Google Drive). All three must be healthy
before the MCP tools respond. Check with:

```bash
docker compose ps
```

If the MCP container is not running, the tools will fail silently. Start it before attempting
any tool calls. The `.mcp.json` is already wired; no manual Claude Code config is needed.

---

## The cardinal rules

1. **Do less, not more.** If a feature is not in the spec, do not add it. When in doubt, open a
   question rather than extending scope. The non-goals in SPEC.md section 1.4 are hard stops.

2. **Do not change the schema without updating SPEC.md section 3 first.** The data model is the
   spine of this project. Schema drift is the most dangerous kind of drift.

3. **Do not add fields to MCP tool schemas without updating SPEC.md section 5 first.** The tool
   surface is what users (and future users) depend on. Undocumented fields create silent contracts.

4. **One process per container. No exceptions.** See SPEC.md section 8.

5. **Every write to the database must be logged.** See SPEC.md section 4.4 for the audit
   convention. If you add a new write path and do not add a log call, the implementation is wrong.

6. **The service layer (`app/src/em_journal/services/`) is the boundary.** API routes call
   services. The MCP server calls services. Nothing else touches the database directly. If you
   find yourself importing the DB module from outside `services/`, stop and refactor.

---

## Commit workflow

This project uses **conventional commits** and tracks progress via `PROGRESS.md`.

### The rule

Every commit that completes a checklist item in `PROGRESS.md` must also check that item in
the same commit. Code change and checkbox land together. This keeps the progress file
trustworthy: a checked box means working, committed code exists for it.

### Conventional commit types used in this project

| Type | When to use |
|---|---|
| `feat` | New user-visible functionality (a working MCP tool, a new web UI page) |
| `fix` | Bug fix in existing functionality |
| `refactor` | Code change with no behavior change |
| `test` | Adding or fixing tests only |
| `docs` | Changes to SPEC.md, PROGRESS.md, AGENTS.md, README.md, or decision records |
| `chore` | Build files, Dockerfiles, docker-compose, pyproject.toml, .gitignore |
| `style` | CSS, formatting, whitespace only |

### Commit granularity

Commits should map to the checklist items in `PROGRESS.md`. A single checklist item
(e.g., "service layer for people.py") is one commit. A verify step that passes after
multiple items is a good moment to pause and confirm nothing is broken before moving on.

Do not group unrelated checklist items into one commit. Do not split a single checklist
item across multiple commits unless the item turns out to be very large (in that case,
split the checklist item first, then commit each piece).

### Procedure for completing a checklist item

1. Implement the work described by the item.
2. Run the verify step for that phase (or the relevant subset of it).
3. Stage the code changes.
4. Edit `PROGRESS.md` to check the box: `- [ ]` becomes `- [x]`.
5. Stage `PROGRESS.md`.
6. Commit both together with a conventional commit message.

Example commit for a service layer item:
```
feat(services): implement people service layer

list_people, get_person, resolve_person, create_person, update_person.
All happy-path tests pass against a real temp SQLite file.
```

### When to move items to the "Completed" section of PROGRESS.md

Move a checked item to the "Completed" section (at the bottom of PROGRESS.md) once the
entire phase it belongs to is done and verified. Include the commit SHA. This keeps the
active checklist short and the history readable.

---

## When implementing a new feature or fixing a bug

1. Read the relevant section(s) of SPEC.md before writing code.
2. Check the Decision Log (SPEC.md Appendix B) for non-obvious choices in the area you're
   touching. If a decision is documented there, do not reverse it without explicitly noting it.
3. Write the service layer function first (input/output types, implementation).
4. Then wire it to the API route and/or MCP tool.
5. Add a smoke test in `tests/` that covers the happy path.
6. Update SPEC.md if anything you implemented differs from what the spec says. The spec is the
   source of truth; if code and spec diverge, one of them is wrong.

---

## Preferred libraries (do not swap without a documented reason)

| Purpose | Library | Notes |
|---|---|---|
| Web framework | FastAPI | Async, typed, Pydantic-native |
| Database access | SQLAlchemy (Core, not ORM) | Thin and explicit; avoid the ORM for this schema size |
| Templating | Jinja2 | Served via FastAPI's TemplateResponse |
| Frontend interactivity | HTMX | No React, no build step |
| MCP server | `mcp` (official Python SDK) | Use HTTP/SSE transport |
| Validation | Pydantic v2 | Used for both API models and MCP tool schemas |
| Backup/cloud sync | rclone | Configured via mounted rclone.conf |
| Linting | ruff | Also used as formatter (replaces black) |
| Type checking | mypy | Strict mode preferred |
| Testing | pytest | Async tests via pytest-asyncio |

---

## What NOT to add (and why)

- **React, Vue, or any JS SPA framework**: HTMX + Jinja2 is the intentional choice. Adding a
  build step would break the "simple to run, simple to contribute to" property.
- **An ORM (e.g., SQLAlchemy ORM, SQLModel, Tortoise)**: The schema is small and stable. Raw
  SQL via SQLAlchemy Core keeps queries readable and migrations explicit.
- **Celery, Redis, or a task queue**: Nothing in v1 needs async background workers. The backup
  container handles its own scheduling.
- **External auth providers**: No OAuth, no JWT, no sessions. The only users are via Tailscale.
- **Migrations via Alembic**: Use plain SQL migration files in `dolt/init/` and a lightweight
  custom runner. Alembic is overkill and adds ceremony for a single-dev project.
- **Logging libraries beyond stdlib `logging`**: Python's built-in logging, structured to stdout,
  is sufficient. Docker captures it.

---

## Test expectations for v1

Tests are intentionally modest. The goal is "does it run and do the obvious thing," not full
coverage. For each new operation:

- One happy-path test using a real (in-memory or temp-file) SQLite database.
- Do NOT mock the database. If a test requires mocking the DB, the design is wrong.
- If testing the MCP server would require mocking the MCP client transport, mark the test
  `@pytest.mark.skip(reason="MCP transport integration test, run manually")` and leave a TODO.
- API route tests use FastAPI's `TestClient`, not a live server.

---

## The ADHD-aware design rule

This tool is built for a manager with ADHD. Surfaces that require the user to remember things
are failures. Specifically:

- The web UI must surface stale data indicators without being asked. If information was not
  confirmed in N days, show it. Do not hide it.
- The backup status must be visible on every page, not buried in a settings screen.
- Forms must have no required fields beyond the person name. Partial data is always accepted.
- If you are building a feature and find yourself thinking "the user can just check X," the
  design is wrong. The system should surface X without being asked.

---

## On the MCP tools specifically

The MCP surface is a public API in the strong sense: any MCP-compatible client can call it,
and you cannot easily roll back a tool schema change once users depend on it. Therefore:

- Tool names are lowercase_snake_case and should be self-explanatory.
- Tool descriptions must be complete sentences suitable for an LLM to read and understand what
  the tool does and when to call it.
- Input fields are required unless they have a documented default. Do not add optional fields
  speculatively; add them when a specific use case requires them.
- Tools that write data must include the written entity's ID in their response, so the caller
  can reference it in follow-up calls.
- No tool should perform more than one logical operation. If you find yourself naming a tool
  `log_one_on_one_and_update_allocation`, split it.
