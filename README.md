<p align="center">
  <img src="assets/logo-mark.svg" width="80" alt="Cadencia" />
</p>

<h1 align="center">Cadencia</h1>
<p align="center"><strong>Keep the rhythm.</strong></p>

<p align="center">
  <img src="https://github.com/apojomovsky/cadencia/actions/workflows/ci.yml/badge.svg" alt="CI" />
  <img src="https://img.shields.io/badge/python-3.12-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker&logoColor=white" alt="Docker Compose" />
  <img src="https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/MCP-compatible-8B5CF6.svg" alt="MCP compatible" />
</p>

<br />

A self-hosted people management journal for engineering managers. Cadencia tracks your direct
reports: allocations, 1:1 history, observations, and open action items. It surfaces stale data
before you have to think to look for it. Everything runs locally via Docker Compose. Your data
never leaves your machine.

---

## Quick start

```bash
git clone https://github.com/apojomovsky/cadencia.git
cd cadencia
make bootstrap   # configure once: DB location, ports, staleness thresholds
make up          # build images and start
```

Open `http://localhost:8080`. Done.

---

## Development

```bash
make setup-dev   # install dev dependencies and git pre-commit hook (run once)
make dev         # start with hot reload
make test        # run the test suite
make lint        # ruff check
make lint-fix    # ruff check --fix
make logs        # follow container logs
make shell       # shell into the app container
make down        # stop the stack
```

Run `make` with no arguments to see all available targets.

---

## MCP tools (Claude Code)

The repo ships `.mcp.json` at the root. Claude Code picks it up automatically when you open a
session from this directory:

```bash
make up
claude
```

| Tool | What it does |
|---|---|
| `list_people` | List all direct reports |
| `get_person` | Full profile by name or ID |
| `add_observation` | Append a tagged observation |
| `log_one_on_one` | Record a 1:1 with notes and action items |
| `update_allocation` | Set or update a client/project allocation |
| `complete_action_item` | Mark an action item done |
| `whats_stale` | Team-wide staleness report |

See `AGENTS.md` for guidance on working with this codebase via an AI agent.

---

## Restoring from a backup

```bash
./scripts/restore.sh                              # interactive: lists and prompts
./scripts/restore.sh cadencia-20260415-030013.db.gz  # restore a specific file
```

The script stops the stack, replaces the database, and exits. Restart with `make up`.

---

## Google Drive backups (optional)

Cadencia backs up the database daily and uploads it to Google Drive via rclone. Without this
setup the app runs fine; backups are skipped silently.

```bash
# Install rclone: https://rclone.org/install/
mkdir -p secrets

rclone config
# Name: gdrive / Type: drive / complete the OAuth flow in your browser

cp ~/.config/rclone/rclone.conf secrets/rclone.conf
make up   # or make down && make up to pick up the new config
```

Backup schedule and destination are set during `make bootstrap` (or editable in `.env`).

---

## Repository layout

```
app/          FastAPI web app and shared service layer
mcp/          MCP server (wraps the service layer)
backup/       Backup container (SQLite online backup + rclone)
assets/       Logo and brand assets
scripts/      bootstrap, restore, dev setup
docs/SPEC.md  Full implementation spec
AGENTS.md     Guidance for AI agents working on this codebase
```

---

## License

Apache 2.0. See [LICENSE](LICENSE).
