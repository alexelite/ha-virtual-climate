#!/usr/bin/env bash
# Sync local -> HA OS and (by default) restart HA Core.
# Usage:
#   ./dev/sync.sh              # sync + restart
#   ./dev/sync.sh --no-restart # doar sync

set -euo pipefail

HOST="${HOST:-ha}"  # folosește aliasul din ~/.ssh/config; poți exporta HOST=...
REMOTE_DIR="/config/custom_components/virtual_climate"

# cale locală către pachetul integrării
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/custom_components/virtual_climate"

RESTART=true
if [[ "${1:-}" == "--no-restart" ]]; then
  RESTART=false
fi

echo "→ Host:       $HOST"
echo "→ Local:      $LOCAL_DIR"
echo "→ Remote:     $REMOTE_DIR"
echo "→ Restart HA: $RESTART"
echo

# asigură-te că folderul există pe host
ssh "$HOST" "mkdir -p '$REMOTE_DIR'"

# sincronizare curată
rsync -avz --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  "$LOCAL_DIR"/ "$HOST":"$REMOTE_DIR"/

echo "✓ Sync complete."

if $RESTART; then
  echo "↻ Restarting Home Assistant Core..."
  if ssh "$HOST" "ha core restart"; then
    echo "✓ HA Core restart triggered."
  else
    echo "⚠️  Nu am reușit să rulez 'ha core restart'. Fă restart din UI (Settings → System → Restart)."
  fi
fi
