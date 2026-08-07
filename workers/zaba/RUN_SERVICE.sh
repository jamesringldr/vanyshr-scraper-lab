#!/usr/bin/env bash
# Start the Zaba scraper service on port 8788.
# Run from the workers/zaba/ directory or pass the path.
#
# Usage:
#   ./workers/zaba/RUN_SERVICE.sh              # prod mode (1 worker)
#   ZABA_DIRECT_FALLBACK=1 ./workers/zaba/RUN_SERVICE.sh  # allow direct fetch fallback

set -euo pipefail
cd "$(dirname "$0")"

PORT="${ZABA_PORT:-8788}"
WORKERS="${ZABA_WORKERS:-1}"

echo "→ Starting zaba-scraper-service on port ${PORT}"

exec uvicorn service:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --log-level info
