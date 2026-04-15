#!/usr/bin/env bash
# Restore EM Journal database from a Google Drive backup.
# See docs/SPEC.md section 7.6 for the documented procedure.

set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
BACKUP_PATH="${BACKUP_PATH:-em-journal-backups}"
VOLUME_NAME="em_journal_data"

log() { echo "[restore] $*"; }
die() { echo "[restore] ERROR: $*" >&2; exit 1; }

command -v rclone >/dev/null 2>&1 || die "rclone is not installed"
command -v docker >/dev/null 2>&1 || die "docker is not installed"

log "Available backups in ${RCLONE_REMOTE}:${BACKUP_PATH}/"
rclone ls "${RCLONE_REMOTE}:${BACKUP_PATH}/" | sort -k2 | tail -20

echo ""
read -rp "Enter the filename to restore (e.g. em-journal-20260415-030000.db.gz): " FILENAME

[[ -n "$FILENAME" ]] || die "No filename provided"

log "Downloading $FILENAME..."
rclone copy "${RCLONE_REMOTE}:${BACKUP_PATH}/${FILENAME}" /tmp/

GZ_PATH="/tmp/${FILENAME}"
DB_PATH="${GZ_PATH%.gz}"

[[ -f "$GZ_PATH" ]] || die "Download failed: $GZ_PATH not found"

log "Decompressing..."
gunzip -c "$GZ_PATH" > "$DB_PATH"
rm -f "$GZ_PATH"

echo ""
echo "WARNING: This will replace the current database in volume '${VOLUME_NAME}'."
read -rp "Are you sure? Type YES to continue: " CONFIRM

[[ "$CONFIRM" == "YES" ]] || { log "Aborted."; exit 0; }

log "Stopping running containers..."
docker compose down 2>/dev/null || true

log "Copying database into volume..."
docker run --rm \
    -v "${VOLUME_NAME}:/data" \
    -v "/tmp:/tmp" \
    alpine \
    cp "/tmp/$(basename "$DB_PATH")" /data/em.db

rm -f "$DB_PATH"

log "Restore complete. Run 'docker compose up -d' to start."
