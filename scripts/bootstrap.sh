#!/usr/bin/env bash
# Cadencia setup wizard.
# Writes .env and, if a custom DB path is chosen, docker-compose.override.yml.
# Run via: make bootstrap
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

B='\033[1m'
C='\033[0;36m'
G='\033[0;32m'
Y='\033[0;33m'
N='\033[0m'

ask() {
    local prompt="$1" default="$2" var="$3"
    printf "${C}%s${N} [${B}%s${N}]: " "$prompt" "$default"
    read -r _ans
    printf -v "$var" '%s' "${_ans:-$default}"
}

ask_yn() {
    local prompt="$1" default="$2" var="$3"
    printf "${C}%s${N} [${B}%s${N}]: " "$prompt" "$default"
    read -r _ans
    _ans="${_ans:-$default}"
    [[ "$_ans" =~ ^[Yy] ]] && printf -v "$var" 'y' || printf -v "$var" 'n'
}

section() { printf "\n${B}--- %s ---${N}\n" "$1"; }

# Detect local timezone offset from UTC (returns e.g. -3, +2, 0)
local_utc_offset() {
    python3 -c "
import datetime, time
offset = -time.timezone if time.daylight == 0 else -time.altzone
print(int(offset / 3600))
" 2>/dev/null || echo "0"
}

# Convert local hour to UTC hour
to_utc_hour() {
    local local_hour="$1" offset="$2"
    python3 -c "print((${local_hour} - ${offset}) % 24)" 2>/dev/null || echo "3"
}

# Detect local timezone name (e.g. "America/Argentina/Buenos_Aires")
local_tz_name() {
    # Try timedatectl first (Linux)
    if command -v timedatectl &>/dev/null; then
        timedatectl show --property=Timezone --value 2>/dev/null && return
    fi
    # Fall back to /etc/timezone
    if [[ -f /etc/timezone ]]; then
        cat /etc/timezone && return
    fi
    # Fall back to TZ env var or UTC
    echo "${TZ:-UTC}"
}

# -----------------------------------------------------------------------

printf "\n${B}Cadencia setup${N}\n"
printf "Writes .env (and docker-compose.override.yml if needed).\n"

if [[ -f "$REPO_ROOT/.env" ]]; then
    printf "\n${Y}.env already exists.${N}\n"
    ask_yn "Overwrite it?" "n" overwrite
    [[ "$overwrite" == "y" ]] || { echo "Aborted. Existing .env kept."; exit 0; }
fi

# --- Database -----------------------------------------------------------
section "Database"
printf "The database is a single SQLite file. Storing it in a host directory\n"
printf "means you can open it directly, back it up with rsync, or inspect it\n"
printf "with any SQLite tool. That's the recommended choice.\n\n"

DEFAULT_DATA_DIR="$HOME/.local/share/cadencia"
ask "Where should the database live?" "$DEFAULT_DATA_DIR" DATA_DIR
DATA_DIR="${DATA_DIR/#\~/$HOME}"
mkdir -p "$DATA_DIR"
printf "${G}Directory ready: %s${N}\n" "$DATA_DIR"

# --- Backup -------------------------------------------------------------
section "Backups"
printf "Cadencia can back up the database daily to Google Drive via rclone.\n"
printf "This is optional. The app runs fine without it.\n\n"

ask_yn "Set up Google Drive backups?" "n" setup_backup

RCLONE_REMOTE=""
BACKUP_PATH="cadencia-backups"
BACKUP_HOUR_UTC=3

if [[ "$setup_backup" == "y" ]]; then
    # Detect available rclone remotes
    if ! command -v rclone &>/dev/null; then
        printf "${Y}rclone is not installed. Skipping backup configuration.${N}\n"
        printf "Install it later from https://rclone.org/install/ then re-run make bootstrap.\n"
        setup_backup="n"
    else
        REMOTES=$(rclone listremotes 2>/dev/null | tr -d ':' | tr '\n' ' ')
        if [[ -z "$REMOTES" ]]; then
            printf "${Y}No rclone remotes configured yet.${N}\n"
            printf "Run 'rclone config' to add a Google Drive remote, then re-run make bootstrap.\n"
            setup_backup="n"
        else
            REMOTE_COUNT=$(echo "$REMOTES" | wc -w)
            if [[ "$REMOTE_COUNT" -eq 1 ]]; then
                RCLONE_REMOTE="${REMOTES// /}"
                printf "Using rclone remote: ${B}%s${N}\n" "$RCLONE_REMOTE"
            else
                printf "Available remotes: ${B}%s${N}\n" "$REMOTES"
                ask "Which remote to use?" "$(echo "$REMOTES" | awk '{print $1}')" RCLONE_REMOTE
            fi

            ask "Folder name inside Google Drive" "cadencia-backups" BACKUP_PATH

            TZ_NAME=$(local_tz_name)
            UTC_OFFSET=$(local_utc_offset)
            LOCAL_DEFAULT=3
            if [[ "$UTC_OFFSET" -ne 0 ]]; then
                # Show a sensible local default (3 AM local time)
                LOCAL_DEFAULT=3
            fi
            printf "Your timezone: ${B}%s${N} (UTC%+d)\n" "$TZ_NAME" "$UTC_OFFSET"
            ask "Run backup at what time? (local, 24h)" "$LOCAL_DEFAULT" backup_local_hour
            BACKUP_HOUR_UTC=$(to_utc_hour "$backup_local_hour" "$UTC_OFFSET")
            printf "Backup will run at %02d:00 local = %02d:00 UTC\n" \
                "$backup_local_hour" "$BACKUP_HOUR_UTC"
        fi
    fi
fi

# --- Staleness thresholds -----------------------------------------------
section "Staleness alerts"
printf "The dashboard flags things that have gone quiet for too long.\n\n"

printf "${B}Allocations:${N} how long since you last confirmed what someone is working on.\n"
ask "Flag as stale after how many days?" "45" ALLOC_STALE

printf "\n${B}1:1s:${N} how long since your last one-on-one with someone.\n"
ask "Flag as overdue after how many days?" "14" OO_STALE

# --- Ports --------------------------------------------------------------
section "Ports"
ask "Web UI port" "8080" APP_PORT
ask "MCP server port" "8081" MCP_PORT

# --- Write .env ---------------------------------------------------------
cat > "$REPO_ROOT/.env" <<EOF
# Generated by make bootstrap on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Edit directly or re-run make bootstrap to regenerate.

# Logical owner ID (leave as "default" for single-user installs)
OWNER_ID=default

# Backup
RCLONE_REMOTE=${RCLONE_REMOTE}
BACKUP_PATH=${BACKUP_PATH}
BACKUP_HOUR=${BACKUP_HOUR_UTC}

# Staleness thresholds (days)
ALLOCATION_STALE_DAYS=${ALLOC_STALE}
ONE_ON_ONE_STALE_DAYS=${OO_STALE}

# Ports
APP_PORT=${APP_PORT}
MCP_PORT=${MCP_PORT}

# Log level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
EOF

printf "\n${G}.env written.${N}\n"

# --- Write docker-compose.override.yml ----------------------------------
OVERRIDE="$REPO_ROOT/docker-compose.override.yml"

cat > "$OVERRIDE" <<EOF
# Auto-generated by make bootstrap on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Delete this file to switch to a Docker named volume instead.
services:
  app:
    volumes:
      - ${DATA_DIR}:/data
      - backup_status:/backup-status:ro
  mcp:
    volumes:
      - ${DATA_DIR}:/data
  backup:
    volumes:
      - ${DATA_DIR}:/data:ro
      - backup_status:/backup-status
      - ./secrets:/secrets:ro
EOF

printf "${G}docker-compose.override.yml written.${N}\n"
printf "Database: ${B}%s/em.db${N}\n" "$DATA_DIR"
printf "\n${G}Done.${N} Run ${B}make up${N} to start.\n\n"
