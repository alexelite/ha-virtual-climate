#!/usr/bin/env bash
# Validate, snapshot, stage and install Virtual Climate over SSH.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_DIR="$REPO_ROOT/custom_components/virtual_climate"
HA_HOST="${HA_HOST:-${HOST:-ha}}"
CONFIG_ROOT="${HA_CONFIG_ROOT:-}"
TEST_PYTHON="${TEST_PYTHON:-python3}"
RESTART=true
DRY_RUN=false
ROLLBACK_ID=""

usage() {
  cat <<'HELP'
Usage: bash dev/sync.sh [--dry-run] [--no-restart] [--host SSH_ALIAS]
                       [--config-root PATH] [--test-python PYTHON]
       bash dev/sync.sh --rollback BACKUP_ID [--host SSH_ALIAS]

Default: tests, component/config backup, staged SHA-256 and HA-runtime import
checks, installation, HA config check, Core restart and API readiness check.
--dry-run performs tests and a read-only file comparison. --no-restart installs
verified files but leaves the currently running Python code active until restart.
Rollback restores component code only; HA .storage is never overwritten.
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-restart) RESTART=false; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --host|--config-root|--test-python|--rollback)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      case "$1" in
        --host) HA_HOST="$2" ;;
        --config-root) CONFIG_ROOT="$2" ;;
        --test-python) TEST_PYTHON="$2" ;;
        --rollback) ROLLBACK_ID="$2" ;;
      esac
      shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
[[ "$HA_HOST" != -* ]] || { echo "Invalid SSH host" >&2; exit 2; }
if [[ "$DRY_RUN" == true && -n "$ROLLBACK_ID" ]]; then
  echo "--dry-run cannot be combined with --rollback" >&2; exit 2
fi
for executable in python3 ssh rsync "$TEST_PYTHON"; do
  command -v "$executable" >/dev/null || { echo "Missing executable: $executable" >&2; exit 1; }
done

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
LOCAL_STAGE="$(mktemp -d "${TMPDIR:-/tmp}/virtual-climate-sync.XXXXXX")"
PREPARED=false

remote() {
  local remote_command
  remote_command="$(python3 -c 'import shlex,sys; print(shlex.join(["python3", "-"] + sys.argv[1:]))' "$@")"
  ssh -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    "$HA_HOST" "$remote_command" < "$SCRIPT_DIR/deploy.py"
}

json_field() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

cleanup() {
  local result=$?
  trap - EXIT
  if [[ "$PREPARED" == true && "$result" -ne 0 ]]; then
    remote abort --config-root "$CONFIG_ROOT" --run-id "$RUN_ID" >/dev/null || true
    echo "Deployment stopped. Recovery files: $CONFIG_ROOT/virtual_climate_backups/$RUN_ID" >&2
  fi
  rm -rf -- "$LOCAL_STAGE"
  exit "$result"
}
trap cleanup EXIT

if [[ -z "$ROLLBACK_ID" ]]; then
  echo "Packaging an immutable component snapshot..."
  python3 "$SCRIPT_DIR/deploy.py" build --source "$LOCAL_DIR" \
    --destination "$LOCAL_STAGE/component" --payload "$LOCAL_STAGE/payload.json"
  echo "Running regression tests..."
  "$TEST_PYTHON" -m unittest discover -s "$REPO_ROOT/tests" -v
  python3 "$SCRIPT_DIR/deploy.py" assert-source --source "$LOCAL_DIR" --payload "$LOCAL_STAGE/payload.json"
fi

INSPECT_ARGS=(inspect)
if [[ -n "$CONFIG_ROOT" ]]; then INSPECT_ARGS+=(--config-root "$CONFIG_ROOT"); fi
HOST_INFO="$(remote "${INSPECT_ARGS[@]}")"
CONFIG_ROOT="$(printf '%s' "$HOST_INFO" | json_field config_root)"
REMOTE_DIR="$(printf '%s' "$HOST_INFO" | json_field target)"
echo "SSH host: $HA_HOST; component: $REMOTE_DIR"
printf 'Installed version: %s\n' "$(printf '%s' "$HOST_INFO" | json_field version)"

if [[ "$DRY_RUN" == true ]]; then
  rsync -anic --delete --exclude '__pycache__/' --exclude '*.pyc' --exclude '*.pyo' \
    --exclude '.DS_Store' -e 'ssh -o BatchMode=yes -o ConnectTimeout=8' \
    "$LOCAL_STAGE/component/" "$HA_HOST:$REMOTE_DIR/"
  echo "Dry run complete. No remote files or settings changed."
  exit 0
fi

PREPARE_ARGS=(prepare --config-root "$CONFIG_ROOT" --run-id "$RUN_ID")
if [[ -n "$ROLLBACK_ID" ]]; then PREPARE_ARGS+=(--from-backup "$ROLLBACK_ID"); fi
PREPARED=true
PREPARE_INFO="$(remote "${PREPARE_ARGS[@]}")"
REMOTE_STAGE="$(printf '%s' "$PREPARE_INFO" | json_field stage)"
REMOTE_PAYLOAD="$(printf '%s' "$PREPARE_INFO" | json_field payload_path)"
echo "Component and integration configuration saved to: $CONFIG_ROOT/virtual_climate_backups/$RUN_ID"

if [[ -z "$ROLLBACK_ID" ]]; then
  rsync -az --delete -e 'ssh -o BatchMode=yes -o ConnectTimeout=8' \
    "$LOCAL_STAGE/component/" "$HA_HOST:$REMOTE_STAGE/"
  rsync -az -e 'ssh -o BatchMode=yes -o ConnectTimeout=8' \
    "$LOCAL_STAGE/payload.json" "$HA_HOST:$REMOTE_PAYLOAD"
fi
echo "Verifying transferred hashes, syntax and imports inside the real HA container..."
remote verify --config-root "$CONFIG_ROOT" --run-id "$RUN_ID"

ACTIVATE_ARGS=(activate --config-root "$CONFIG_ROOT" --run-id "$RUN_ID")
if [[ "$RESTART" == false ]]; then ACTIVATE_ARGS+=(--no-restart); fi
echo "Installing, checking HA configuration and restarting Core when requested..."
RESULT="$(remote "${ACTIVATE_ARGS[@]}")"
PREPARED=false
mkdir -p "$REPO_ROOT/local/deployments"
printf '%s\n' "$RESULT" > "$REPO_ROOT/local/deployments/$RUN_ID.json"
printf '%s\n' "$RESULT"
echo "Deployment record: local/deployments/$RUN_ID.json"
echo "To restore previous component code: bash dev/sync.sh --host $HA_HOST --config-root $CONFIG_ROOT --rollback $RUN_ID"
