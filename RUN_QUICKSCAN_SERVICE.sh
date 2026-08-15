#!/usr/bin/env bash
# Start the quickscan service on port 8790.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${QUICKSCAN_PORT:-8790}"
WORKERS="${QUICKSCAN_WORKERS:-1}"
echo "→ Starting quickscan-service on port ${PORT}"
exec .venv-local/bin/uvicorn quickscan_service:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --log-level info
