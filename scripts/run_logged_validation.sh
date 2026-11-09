#!/usr/bin/env bash
# Keep the already authorized local run observable outside a tool session.
set -uo pipefail
CASMI_LOGGED_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$CASMI_LOGGED_ROOT/scripts/linux_env.sh" || exit 1
if [[ "$#" -lt 2 ]]; then
  echo 'Usage: run_logged_validation.sh WORKSPACE_LOG PYTHON_SCRIPT [ARGS...]' >&2
  exit 2
fi
CASMI_RUN_LOG="$1"
shift
CASMI_RUN_LOG="$(realpath -m -- "$CASMI_RUN_LOG")"
case "$CASMI_RUN_LOG" in
  "$CASMI_LOGGED_ROOT"/*) ;;
  *) echo 'Log must remain inside the D: workspace' >&2; exit 2 ;;
esac
if [[ -e "$CASMI_RUN_LOG" || -e "$CASMI_RUN_LOG.pid" ]]; then
  echo 'Use a fresh log path; existing run evidence is preserved' >&2
  exit 2
fi
mkdir -p -- "$(dirname -- "$CASMI_RUN_LOG")"
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$CASMI_RUN_LOG.started_utc"
printf '%s\n' "$$" > "$CASMI_RUN_LOG.supervisor_pid"
"$CASMI_LOGGED_ROOT/.venv-linux/bin/python" "$@" > "$CASMI_RUN_LOG" 2>&1 &
CASMI_RUN_PID=$!
printf '%s\n' "$CASMI_RUN_PID" > "$CASMI_RUN_LOG.pid"
CASMI_RUN_STATUS=0
wait "$CASMI_RUN_PID" || CASMI_RUN_STATUS=$?
printf '%s\n' "$CASMI_RUN_STATUS" > "$CASMI_RUN_LOG.exit_code"
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$CASMI_RUN_LOG.finished_utc"
exit "$CASMI_RUN_STATUS"
