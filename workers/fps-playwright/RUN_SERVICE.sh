#!/usr/bin/env bash
# Run the FPS HTTP service (service.py) in the foreground.
#
# First-time setup (same venv the smoke test already uses, or a fresh one):
#   python3 -m venv .venv && . .venv/bin/activate
#   pip install -r requirements.txt
#   python -m camoufox fetch
#
# Config via env or workers/fps-playwright/.env:
#   FPS_SERVICE_TOKEN     bearer token required on POST /v1/fps/search (unset = no auth, dev only)
#   FPS_SMOKE_TIMEOUT_S   max seconds for the Camoufox harvest step (default 120)
#   FPS_KEEP_ARTIFACTS=1  keep per-request out dirs (screenshots/HTML/cookies) instead of deleting them
#   PORT                  listen port (default 8787)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SRC"

VENV="${VENV:-.venv}"
if [ ! -d "$VENV" ]; then
  echo "ERROR: ${SRC}/${VENV} missing. Install first:" >&2
  echo "  python3 -m venv ${VENV} && . ${VENV}/bin/activate && pip install -r requirements.txt && python -m camoufox fetch" >&2
  exit 1
fi
# shellcheck disable=SC1091
. "${VENV}/bin/activate"

PORT="${PORT:-8787}"
echo "→ fps-scraper-service listening on :${PORT}"
exec python -m uvicorn service:app --host 0.0.0.0 --port "${PORT}"
