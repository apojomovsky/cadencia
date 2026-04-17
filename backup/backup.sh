#!/usr/bin/env bash
# Cadencia backup script.
# Runs on startup (writes sentinel immediately) then loops daily at BACKUP_HOUR.
# Skips rclone upload if config is missing (safe for development).

set -euo pipefail

SENTINEL="${BACKUP_STATUS_PATH:-/backup-status/last.json}"
DB_PATH="${DB_PATH:-/data/em.db}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
BACKUP_DEST_PATH="${BACKUP_PATH:-cadencia-backups}"
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

apply_retention() {
    # Keep all backups from the last 30 days.
    # Keep the most recent backup per ISO week for days 31-365.
    # Delete anything older than 365 days.
    if [[ ! -f "$RCLONE_CONFIG_FILE" ]]; then
        return 0
    fi

    log "Applying retention policy..."

    local today_epoch
    today_epoch=$(date -u +%s)
    local cutoff_30=$(( today_epoch - 30 * 86400 ))
    local cutoff_365=$(( today_epoch - 365 * 86400 ))

    local files
    files=$(rclone --config="$RCLONE_CONFIG_FILE" lsf "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/" 2>/dev/null \
        | grep -E '^cadencia-[0-9]{8}-[0-9]{6}\.tar\.gz$' \
        | sort) || true

    if [[ -z "$files" ]]; then
        return 0
    fi

    declare -A week_kept
    local -a to_delete=()

    while IFS= read -r fname; do
        local datepart
        datepart=$(echo "$fname" | sed 's/cadencia-\([0-9]\{8\}\)-.*/\1/')
        local y="${datepart:0:4}" m="${datepart:4:2}" d="${datepart:6:2}"

        local file_epoch
        file_epoch=$(date -u -d "${y}-${m}-${d}" +%s 2>/dev/null) || continue

        if (( file_epoch >= cutoff_30 )); then
            # Last 30 days: keep all
            continue
        elif (( file_epoch < cutoff_365 )); then
            # Older than 365 days: delete
            to_delete+=("$fname")
        else
            # 31-365 days: keep most recent per week
            local week_key
            week_key=$(date -u -d "${y}-${m}-${d}" +%G-%V 2>/dev/null) || continue

            if [[ -n "${week_kept[$week_key]+_}" ]]; then
                # Files are sorted ascending; current file is newer, replace older
                to_delete+=("${week_kept[$week_key]}")
            fi
            week_kept[$week_key]="$fname"
        fi
    done <<< "$files"

    for fname in "${to_delete[@]:-}"; do
        [[ -z "$fname" ]] && continue
        log "Retention: deleting ${fname}"
        rclone --config="$RCLONE_CONFIG_FILE" delete "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/${fname}" || true
    done

    log "Retention policy applied."
}

run_backup() {
    if [[ ! -f "$DB_PATH" ]]; then
        log "Database not found at $DB_PATH, skipping backup."
        write_sentinel "false" "null" "db not found"
        return 0
    fi

    local ts
    ts="$(date -u +%Y%m%d-%H%M%S)"
    local tmp_db="/tmp/em.db"
    local tar_file="/tmp/cadencia-${ts}.tar.gz"
    local dest_name="cadencia-${ts}.tar.gz"

    log "Starting backup..."

    # SQLite online backup (safe under concurrent reads/writes)
    sqlite3 "$DB_PATH" ".backup ${tmp_db}"

    # Bundle db and context directory into a single archive
    local tar_args=("-czf" "$tar_file" "-C" "/tmp" "em.db")
    if [[ -d "/data/context" ]]; then
        tar_args+=("-C" "/data" "context")
    fi
    tar "${tar_args[@]}"
    rm -f "$tmp_db"

    log "Backup created: ${tar_file} ($(du -sh "$tar_file" | cut -f1))"

    if [[ -f "$RCLONE_CONFIG_FILE" ]]; then
        log "Uploading to ${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/${dest_name}"
        rclone --config="$RCLONE_CONFIG_FILE" copy "$tar_file" "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/"
        log "Upload complete."
        write_sentinel "true" "$dest_name"
        apply_retention
    else
        log "rclone config not found at ${RCLONE_CONFIG_FILE}. Skipping upload (dev mode)."
        write_sentinel "true" "$dest_name"
    fi

    rm -f "$tar_file"
}

# Write startup sentinel immediately so the Docker healthcheck passes
write_sentinel "true" "null"
log "Backup service started. Will run daily at ${BACKUP_HOUR}:00 UTC."

# Main loop
while true; do
    current_hour="$(date +%-H)"
    if [[ "$current_hour" -eq "$BACKUP_HOUR" ]]; then
        run_backup || write_sentinel "false" "null" "backup failed: see container logs"
        # Sleep 61 minutes so we don't re-fire in the same hour window
        sleep 3660
    else
        sleep 60
    fi
done
