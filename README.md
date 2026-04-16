<p align="center">
  <img src="assets/logo-mark.svg" width="80" alt="Cadencia" />
</p>

<h1 align="center">Cadencia</h1>
<p align="center"><strong>Keep the rhythm.</strong></p>

<p align="center">
  <img src="https://github.com/apojomovsky/cadencia/actions/workflows/ci.yml/badge.svg" alt="CI" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0" />
  <img src="https://img.shields.io/badge/python-3.12-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker&logoColor=white" alt="Docker Compose" />
  <img src="https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI" />
</p>

<br />

A self-hosted people management journal for engineering managers. Cadencia tracks your direct
reports: their allocations, 1:1 history, observations, and open action items. It surfaces
stale data before you have to think to look for it.

It runs entirely on your machine via Docker Compose. Your data never leaves. An MCP server lets
you query and capture notes directly from a Claude conversation, and a web UI gives you a
full-team dashboard and per-person detail view for when you want to browse rather than ask.

---

## Features

- **Dashboard:** stale allocations, overdue 1:1s, and aging action items surfaced automatically on every load
- **Per-person view:** current allocation, open action items, recent observations, 1:1 log, and allocation history in one page
- **MCP server:** seven tools callable from Claude Code or any MCP-compatible client
- **Local-first:** SQLite on a named Docker volume; no external database, no cloud account required to run
- **Daily backups:** automated SQLite online backup, gzipped and uploaded to Google Drive via rclone
- **ADHD-aware design:** the system brings stale data forward; nothing requires you to remember to check

---

## Prerequisites

- Docker and Docker Compose v2
- rclone (for Google Drive backups; optional for local-only use)

---

## Quick start

### 1. Clone and configure

```bash
git clone https://github.com/apojomovsky/cadencia.git
cd cadencia
cp .env.example .env
```

Edit `.env` to adjust defaults (backup schedule, staleness thresholds, etc.).

### 2. Set up rclone for Google Drive backups

```bash
# Install rclone: https://rclone.org/install/
mkdir -p secrets

# Configure a remote named "gdrive"
rclone config
# Follow the prompts:
#   Name: gdrive
#   Type: drive (Google Drive)
#   Complete the OAuth flow in your browser

cp ~/.config/rclone/rclone.conf secrets/rclone.conf
```

If `secrets/rclone.conf` is absent, the backup container runs but skips the upload step. Safe for local development.

### 3. Start

```bash
make up
```

First run builds all three images. Open `http://localhost:8080` once the containers are healthy (about 30 seconds).

### 4. Verify

```bash
docker compose ps

curl http://localhost:8080/api/health
# {"status": "ok", "version": "0.1.0"}

curl http://localhost:8081/health
# {"status": "ok"}
```

---

## Development

```bash
make setup-dev   # install dev dependencies and git pre-commit hook (run once)
make dev         # start with hot reload (dev overlay)
make test        # run the test suite inside the app container
make lint        # ruff check
make lint-fix    # ruff check --fix
make logs        # follow container logs
make shell       # open a shell in the app container
make down        # stop the stack
```

Run `make` with no arguments to see all available commands.

---

## Using with Claude Code

The repo ships `.mcp.json` at the root. Claude Code picks it up automatically when you open a
session from this directory. Start the stack first, then open a Claude conversation:

```bash
make up
claude  # or open the project in your IDE with Claude Code
```

The seven MCP tools become available immediately:

| Tool | What it does |
|---|---|
| `list_people` | List all direct reports (filter by status) |
| `get_person` | Full profile for one person by name or ID |
| `add_observation` | Append a tagged observation |
| `log_one_on_one` | Record a 1:1 with notes and action items |
| `update_allocation` | Set or update a client/project allocation |
| `complete_action_item` | Mark an action item done with optional notes |
| `whats_stale` | Team-wide staleness report |

See `AGENTS.md` for guidance on working with this codebase via an AI agent.

---

## Restoring from a backup

```bash
# Interactive: lists available backups and prompts for selection
./scripts/restore.sh

# Direct: restore a specific file
./scripts/restore.sh cadencia-20260415-030013.db.gz
```

The restore script stops the running stack, replaces the database volume, and exits cleanly.
Restart with `make up`.

---

## Repository layout

```
app/          FastAPI web app and shared service layer
mcp/          MCP server (wraps the service layer)
backup/       Backup container (SQLite online backup + rclone)
assets/       Logo and brand assets
db/init/      SQL migration files
scripts/      Utility scripts (restore)
docs/SPEC.md  Full implementation spec
AGENTS.md     Guidance for AI agents working on this codebase
PROGRESS.md   Implementation checklist
```

---

## License

Apache 2.0. See [LICENSE](LICENSE).
