#!/usr/bin/env bash
# Cadencia restore script.
# Restores the database and context files from a Google Drive backup.
#
# Usage (run from repo root):
#   ./scripts/restore.sh                                          # lists backups, prompts
#   ./scripts/restore.sh cadencia-20260415-030013.tar.gz         # restore specific file

set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
BACKUP_DEST_PATH="${BACKUP_PATH:-cadencia-backups}"
RCLONE_CONFIG_FILE="${RCLONE_CONFIG:-./secrets/rclone.conf}"
VOLUME_NAME="cadencia_data"

log() { echo "==> $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

command -v rclone >/dev/null 2>&1 || die "rclone is not installed."
command -v docker  >/dev/null 2>&1 || die "docker is not installed."
[[ -f "$RCLONE_CONFIG_FILE" ]] || die "rclone config not found at ${RCLONE_CONFIG_FILE}. Run 'rclone config' first and copy to secrets/rclone.conf."

BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" ]]; then
    log "Available backups in ${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/ (newest first):"
    echo ""
    rclone --config="$RCLONE_CONFIG_FILE" lsf "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/" \
        | grep -E '^cadencia-.*\.(tar\.gz|db\.gz)$' \
        | sort -r \
        | head -20
    echo ""
    read -rp "Enter filename to restore (Ctrl+C to cancel): " BACKUP_FILE
fi

[[ -n "$BACKUP_FILE" ]] || die "No backup file specified."

log "Selected: ${BACKUP_FILE}"
echo ""
echo "  WARNING: This will REPLACE the current database and context files."
echo "  The running stack will be stopped first."
echo "  Any data written after this backup was taken will be lost."
echo ""
read -rp "Type 'yes' to continue: " confirm
[[ "$confirm" == "yes" ]] || { echo "Aborted."; exit 0; }

TMP_FILE="/tmp/${BACKUP_FILE}"

log "Downloading ${BACKUP_FILE}..."
rclone --config="$RCLONE_CONFIG_FILE" copy \
    "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/${BACKUP_FILE}" /tmp/
[[ -f "$TMP_FILE" ]] || die "Download failed: file not found at ${TMP_FILE}"

log "Stopping docker compose stack..."
docker compose down

docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1 \
    || docker volume create "$VOLUME_NAME"

if [[ "$BACKUP_FILE" == *.tar.gz ]]; then
    log "Extracting database and context files from archive..."
    tar -xzf "$TMP_FILE" -C /tmp em.db

    # Restore database
    docker run --rm \
        -v "${VOLUME_NAME}:/data" \
        -v "/tmp:/tmp" \
        alpine cp /tmp/em.db /data/em.db
    rm -f /tmp/em.db

    # Restore context directory if present in archive
    if tar -tzf "$TMP_FILE" | grep -q '^context/'; then
        log "Restoring context directory..."
        rm -rf /tmp/context
        tar -xzf "$TMP_FILE" -C /tmp context
        docker run --rm \
            -v "${VOLUME_NAME}:/data" \
            -v "/tmp:/tmp" \
            alpine sh -c "rm -rf /data/context && cp -r /tmp/context /data/context"
        rm -rf /tmp/context
    else
        log "No context directory in archive; skipping context restore."
    fi

elif [[ "$BACKUP_FILE" == *.db.gz ]]; then
    log "Legacy format detected (.db.gz): restoring database only."
    TMP_DB="/tmp/${BACKUP_FILE%.gz}"
    gunzip -f "$TMP_FILE"
    [[ -f "$TMP_DB" ]] || die "Decompression failed."

    docker run --rm \
        -v "${VOLUME_NAME}:/data" \
        -v "/tmp:/tmp" \
        alpine cp "/tmp/$(basename "$TMP_DB")" /data/em.db
    rm -f "$TMP_DB"

    log "Note: context files were not included in legacy backups and were not restored."
else
    die "Unrecognized backup format: ${BACKUP_FILE}"
fi

rm -f "$TMP_FILE"

log "Restore complete. Start the stack with: docker compose up -d"
