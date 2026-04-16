#!/usr/bin/env bash
# One-time dev setup: installs the git pre-commit hook.
# Run via: make setup-dev  (which also installs Python dev deps first)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SRC="$REPO_ROOT/scripts/pre-commit"
HOOK_DEST="$REPO_ROOT/.git/hooks/pre-commit"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
    echo "Not a git repository. Skipping hook installation."
    exit 0
fi

cp "$HOOK_SRC" "$HOOK_DEST"
chmod +x "$HOOK_DEST"
echo "Pre-commit hook installed at .git/hooks/pre-commit"
