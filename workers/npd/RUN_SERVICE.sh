#!/usr/bin/env bash
# Start NPD scraper service on port 8789.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${NPD_PORT:-8789}"
WORKERS="${NPD_WORKERS:-1}"
echo "→ Starting npd-scraper-service on port ${PORT}"
exec uvicorn service:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --log-level info
