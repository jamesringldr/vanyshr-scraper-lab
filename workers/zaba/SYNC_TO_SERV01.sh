#!/usr/bin/env bash
# Sync workers/zaba → serv-01:C:\Users\scraper\zaba-scraper over Tailscale SSH.
# Does NOT overwrite remote .env (secrets stay on the box).
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
HOST="${ZABA_SSH_HOST:-serv-01}"
REMOTE="${ZABA_REMOTE_DIR:-C:/Users/scraper/zaba-scraper}"

echo "→ Sync $SRC → ${HOST}:${REMOTE}"
ssh -o BatchMode=yes "$HOST" "if not exist \"${REMOTE//\//\\}\" mkdir \"${REMOTE//\//\\}\""

# scp individual files (avoid clobbering .env)
for f in service.py zaba_scraper.py requirements.txt RUN_SERVICE.bat RUN_SERVICE.sh; do
  if [ -f "$SRC/$f" ]; then
    scp -o BatchMode=yes "$SRC/$f" "${HOST}:${REMOTE}/$f"
    echo "  ok $f"
  fi
done

# optional example only
if [ -f "$SRC/move.env.example" ]; then
  scp -o BatchMode=yes "$SRC/move.env.example" "${HOST}:${REMOTE}/.env.example" 2>/dev/null || true
elif [ -f "$SRC/.env.example" ]; then
  scp -o BatchMode=yes "$SRC/.env.example" "${HOST}:${REMOTE}/.env.example"
fi

echo "→ Done. Restart service on serv-01 if it is running."
echo "   ssh $HOST \"cd /d C:\\\\Users\\\\scraper\\\\zaba-scraper && RUN_SERVICE.bat\""
