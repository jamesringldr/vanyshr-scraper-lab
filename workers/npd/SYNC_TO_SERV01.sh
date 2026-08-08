#!/usr/bin/env bash
# Sync workers/npd → serv-01:C:\Users\scraper\npd-scraper over Tailscale SSH.
# Does NOT overwrite remote .env.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
HOST="${NPD_SSH_HOST:-serv-01}"
REMOTE="${NPD_REMOTE_DIR:-C:/Users/scraper/npd-scraper}"

echo "→ Sync $SRC → ${HOST}:${REMOTE}"
ssh -o BatchMode=yes "$HOST" "if not exist \"${REMOTE//\//\\}\" mkdir \"${REMOTE//\//\\}\""

for f in service.py npd_scraper.py requirements.txt RUN_SERVICE.bat RUN_SERVICE.sh _run_logged.bat start_detached.py; do
  if [ -f "$SRC/$f" ]; then
    scp -o BatchMode=yes "$SRC/$f" "${HOST}:${REMOTE}/$f"
    echo "  ok $f"
  fi
done

if [ -f "$SRC/move.env.example" ]; then
  scp -o BatchMode=yes "$SRC/move.env.example" "${HOST}:${REMOTE}/.env.example" 2>/dev/null || true
fi

echo "→ Done. Create .env on box if missing, then start:"
echo "   ssh $HOST \"cd /d C:\\\\Users\\\\scraper\\\\npd-scraper && RUN_SERVICE.bat\""
echo "   or Task Scheduler → NpdScraper → _run_logged.bat"
