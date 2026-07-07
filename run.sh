#!/usr/bin/env bash
#
# run.sh
#
# Wrapper script intended to be triggered by cron once a day at 00:00.

# Install with:
#   crontab -e
#   0 0 * * * /path/to/run.sh >> /path/to/logs/cron.log 2>&1
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"


ENV_FILE="${SCRIPT_DIR}/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -o allexport
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +o allexport
fi

DATE_FROM="$(date -u -d 'yesterday' +%Y-%m-%d)"
DATE_TO="$(date -u +%Y-%m-%d)"

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Running Nomba reconciliation for ${DATE_FROM} -> ${DATE_TO}"

PYTHON_BIN="${SCRIPT_DIR}/venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python3"
fi

"$PYTHON_BIN" "${SCRIPT_DIR}/fetch_missing_transactions.py" \
    --date-from "$DATE_FROM" \
    --date-to "$DATE_TO"

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Done."