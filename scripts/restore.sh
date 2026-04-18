#!/usr/bin/env bash
# Cadencia restore script.
# Restores the database and context files from a Google Drive backup.
#
# Usage (run from repo root):
#   ./scripts/restore.sh                                          # lists Drive backups, prompts
#   ./scripts/restore.sh cadencia-20260415-030013.tar.gz         # restore by name from Drive
#   ./scripts/restore.sh ~/Downloads/cadencia-20260415.tar.gz   # restore from local file

set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
BACKUP_DEST_PATH="${BACKUP_PATH:-cadencia-backups}"
RCLONE_CONFIG_FILE="${RCLONE_CONFIG:-./secrets/rclone.conf}"
VOLUME_NAME="cadencia_data"

log() { echo "==> $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is not installed."

BACKUP_FILE="${1:-}"
LOCAL_FILE=""

if [[ -n "$BACKUP_FILE" && -f "$BACKUP_FILE" ]]; then
    LOCAL_FILE="$BACKUP_FILE"
    BACKUP_FILE="$(basename "$LOCAL_FILE")"
fi

if [[ -z "$BACKUP_FILE" ]]; then
    [[ -f "$RCLONE_CONFIG_FILE" ]] || die "rclone config not found at ${RCLONE_CONFIG_FILE}. Run 'rclone config' first and copy to secrets/rclone.conf."
    command -v rclone >/dev/null 2>&1 || die "rclone is not installed."
    mapfile -t BACKUPS < <(
        rclone --config="$RCLONE_CONFIG_FILE" lsf "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/" \
            | grep -E '^cadencia-.*\.(tar\.gz|db\.gz)$' \
            | sort -r \
            | head -20
    )
    [[ ${#BACKUPS[@]} -gt 0 ]] || die "No backups found in ${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/"
    LATEST="${BACKUPS[0]}"
    log "Available backups (newest first):"
    echo ""
    for f in "${BACKUPS[@]}"; do
        if [[ "$f" == "$LATEST" ]]; then
            echo "  * ${f}  [most recent]"
        else
            echo "    ${f}"
        fi
    done
    echo ""
    read -rp "Enter filename to restore, or press Enter for most recent [${LATEST}]: " BACKUP_FILE
    BACKUP_FILE="${BACKUP_FILE:-$LATEST}"
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

if [[ -n "$LOCAL_FILE" ]]; then
    log "Using local file: ${LOCAL_FILE}"
    cp "$LOCAL_FILE" "$TMP_FILE"
else
    [[ -f "$RCLONE_CONFIG_FILE" ]] || die "rclone config not found at ${RCLONE_CONFIG_FILE}. Run 'rclone config' first and copy to secrets/rclone.conf."
    command -v rclone >/dev/null 2>&1 || die "rclone is not installed."
    log "Downloading ${BACKUP_FILE} from Google Drive..."
    rclone --config="$RCLONE_CONFIG_FILE" copy \
        "${RCLONE_REMOTE}:${BACKUP_DEST_PATH}/${BACKUP_FILE}" /tmp/
    [[ -f "$TMP_FILE" ]] || die "Download failed: file not found at ${TMP_FILE}"
fi

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

log "Restore complete. Start the stack with: make up"
