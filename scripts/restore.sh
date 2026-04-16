#!/usr/bin/env bash
# Cadencia restore script.
# Restores the database from a Google Drive backup.
#
# Usage (run from repo root):
#   ./scripts/restore.sh                                     # lists backups, prompts
#   ./scripts/restore.sh cadencia-20260415-030013.db.gz   # restore specific file

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
        | grep -E '^cadencia-.*\.db\.gz$' \
        | sort -r \
        | head -20
    echo ""
    read -rp "Enter filename to restore (Ctrl+C to cancel): " BACKUP_FILE
fi

[[ -n "$BACKUP_FILE" ]] || die "No backup file specified."

log "Selected: ${BACKUP_FILE}"
echo ""
echo "  WARNING: This will REPLACE the current database."
echo "  The running stack will be stopped first."
echo "  Any data written after this backup was taken will be lost."
echo ""
read -rp "Type 'yes' to continue: " confirm
[[ "$confirm" == "yes" ]] || { echo "Aborted."; exit 0; }

TMP_GZ="/tmp/${BACKUP_FILE}"
TMP_DB="/tmp/${BACKUP_FILE%.gz}"

log "Downloading ${BACKUP_FILE}..."
rclone --config="$RCLONE_CONFIG_FILE" copy \
    "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/${BACKUP_FILE}" /tmp/
[[ -f "$TMP_GZ" ]] || die "Download failed: file not found at ${TMP_GZ}"

log "Decompressing..."
gunzip -f "$TMP_GZ"
[[ -f "$TMP_DB" ]] || die "Decompression failed."

log "Stopping docker compose stack..."
docker compose down

docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1 \
    || docker volume create "$VOLUME_NAME"

log "Copying database into volume ${VOLUME_NAME}..."
docker run --rm \
    -v "${VOLUME_NAME}:/data" \
    -v "/tmp:/tmp" \
    alpine \
    cp "/tmp/$(basename "$TMP_DB")" /data/em.db

rm -f "$TMP_DB"

log "Restore complete. Start the stack with: docker compose up -d"
