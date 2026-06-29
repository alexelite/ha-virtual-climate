#!/usr/bin/env bash
# Watch local files and auto-sync (plus restart by default).
# Dependințe recomandate: 'entr' (sudo apt-get install entr) sau 'fswatch'.
#
# Usage:
#   ./dev/watch.sh              # watch + sync + restart
#   ./dev/watch.sh --no-restart # watch + sync (fără restart)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/custom_components/virtual_climate"

RESTART_FLAG=""
if [[ "${1:-}" == "--no-restart" ]]; then
  RESTART_FLAG="--no-restart"
fi

# preferă 'entr', altfel încearcă 'fswatch'
if command -v entr >/dev/null 2>&1; then
  echo "👀 Watching with 'entr'…"
  # listă de fișiere filtrată
  find "$LOCAL_DIR" -type f \
    ! -path '*/.git/*' \
    ! -path '*/__pycache__/*' \
    ! -path '*/.pytest_cache/*' \
    ! -name '*.pyc' \
    ! -name '*.pyo' \
  | entr -r bash -c "
      echo '…change detected → syncing'
      \"$SCRIPT_DIR/sync.sh\" $RESTART_FLAG
    "
elif command -v fswatch >/dev/null 2>&1; then
  echo "👀 Watching with 'fswatch'…"
  fswatch -o "$LOCAL_DIR" | while read -r _; do
    echo '…change detected → syncing'
    "$SCRIPT_DIR/sync.sh" $RESTART_FLAG
  done
else
  echo "❌ Nu am găsit 'entr' sau 'fswatch'. Instalează una dintre ele:"
  echo "    sudo apt-get install entr"
  echo "    # sau"
  echo "    brew install fswatch   # pe macOS"
  exit 1
fi
