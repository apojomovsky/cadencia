# EM Journal

A self-hosted people management journal for engineering managers. Stores structured notes
about direct reports and answers natural-language questions via an MCP server. Built for
single-user local use.

See `docs/SPEC.md` for the full design, and `PROGRESS.md` for implementation status.

---

## Prerequisites

- Docker and Docker Compose v2
- rclone (for Google Drive backups)

---

## First-time setup

### 1. Copy the environment file

```bash
cp .env.example .env
```

Edit `.env` if you want to change defaults (backup schedule, staleness thresholds, etc.).

### 2. Set up rclone for Google Drive backups

```bash
# Install rclone if not already installed
# https://rclone.org/install/

# Create the secrets directory (gitignored)
mkdir -p secrets

# Configure a Google Drive remote named "gdrive"
rclone config
# Follow the interactive prompts to add a new remote:
#   Name: gdrive
#   Type: drive (Google Drive)
#   Complete the OAuth flow in your browser

# Copy the resulting config to the secrets directory
cp ~/.config/rclone/rclone.conf secrets/rclone.conf
```

The backup container mounts `./secrets/` at runtime. If `secrets/rclone.conf` is missing,
the backup script runs but skips the upload step (safe for development).

### 3. Start the stack

```bash
docker compose up -d
```

First run builds all three images. Subsequent starts are fast.

### 4. Verify

```bash
docker compose ps
# All three services should show status: healthy (after ~30s)

curl http://localhost:8080/api/health
# {"status": "ok", "version": "0.1.0"}

curl http://localhost:8081/health
# {"status": "ok"}
```

---

## Development

For hot reload (source code changes reflected without rebuilding):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

---

## Using the MCP tools with Claude Code

The repo ships a `.mcp.json` at the root that points Claude Code at the MCP server:

```json
{
  "mcpServers": {
    "em-journal": {
      "type": "sse",
      "url": "http://localhost:8081/sse"
    }
  }
}
```

Claude Code picks this up automatically when you open a session from the repo directory.
The stack must be running first (`docker compose up -d`). All seven tools become available
in the conversation: `list_people`, `get_person`, `add_observation`, `log_one_on_one`,
`update_allocation`, `complete_action_item`, and `whats_stale`.

See `AGENTS.md` for full guidance on how to work with this codebase via an AI agent.

---

## Restoring from a backup

See `scripts/restore.sh` for the step-by-step restore procedure, or follow the manual
steps in `docs/SPEC.md` section 7.6.

---

## Repository layout

```
app/          FastAPI web app and shared service layer
mcp/          MCP server (wraps the service layer)
backup/       Backup container (SQLite online backup + rclone)
db/init/      SQL migration files
scripts/      Utility scripts (restore, bootstrap)
docs/SPEC.md  Full implementation spec
AGENTS.md     Guidance for AI agents implementing this codebase
PROGRESS.md   Implementation checklist
```
