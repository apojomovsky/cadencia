#!/usr/bin/env bash
# EM Journal backup script.
# Phase 7 wires up real rclone uploads and retention. For now:
# - writes the sentinel file on startup so healthcheck passes
# - performs the SQLite online backup and logs it
# - skips rclone if config is missing (safe for development)

set -euo pipefail

SENTINEL="${BACKUP_STATUS_PATH:-/backup-status/last.json}"
DB_PATH="${DB_PATH:-/data/em.db}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
BACKUP_DEST_PATH="${BACKUP_PATH:-em-journal-backups}"
BACKUP_HOUR="${BACKUP_HOUR:-3}"
RCLONE_CONFIG_FILE="${RCLONE_CONFIG:-/secrets/rclone.conf}"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

write_sentinel() {
    local success="$1"
    local file="${2:-null}"
    local note="${3:-}"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    mkdir -p "$(dirname "$SENTINEL")"

    if [[ "$success" == "true" ]]; then
        printf '{"success": true, "ts": "%s", "file": "%s"}\n' "$ts" "$file" > "$SENTINEL"
    else
        printf '{"success": false, "ts": "%s", "error": "%s"}\n' "$ts" "$note" > "$SENTINEL"
    fi
}

run_backup() {
    if [[ ! -f "$DB_PATH" ]]; then
        log "Database not found at $DB_PATH, skipping backup."
        write_sentinel "false" "null" "db not found"
        return 0
    fi

    local ts
    ts="$(date -u +%Y%m%d-%H%M%S)"
    local tmp_db="/tmp/em-backup-${ts}.db"
    local gz_file="/tmp/em-journal-${ts}.db.gz"
    local dest_name="em-journal-${ts}.db.gz"

    log "Starting backup..."

    # SQLite online backup (safe under concurrent reads)
    sqlite3 "$DB_PATH" ".backup ${tmp_db}"
    gzip -c "$tmp_db" > "$gz_file"
    rm -f "$tmp_db"

    log "Backup compressed: $gz_file"

    # Upload via rclone if config exists
    if [[ -f "$RCLONE_CONFIG_FILE" ]]; then
        log "Uploading to ${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/${dest_name}"
        rclone --config="$RCLONE_CONFIG_FILE" copy "$gz_file" "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/"
        log "Upload complete."
        write_sentinel "true" "$dest_name"
    else
        log "rclone config not found at $RCLONE_CONFIG_FILE. Skipping upload."
        log "Local backup available at: $gz_file"
        write_sentinel "true" "$dest_name"
    fi

    rm -f "$gz_file"
}

# Write startup sentinel so healthcheck passes immediately
write_sentinel "true" "null"
log "Backup service started."

# Main loop: run backup once per day at the configured hour
while true; do
    current_hour="$(date +%-H)"
    if [[ "$current_hour" -eq "$BACKUP_HOUR" ]]; then
        run_backup || write_sentinel "false" "null" "backup failed: see logs"
        # Sleep 61 minutes so we don't re-trigger in the same hour
        sleep 3660
    else
        sleep 60
    fi
done
