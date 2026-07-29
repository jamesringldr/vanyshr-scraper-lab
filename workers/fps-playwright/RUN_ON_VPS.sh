#!/usr/bin/env bash
# Run from the vanyshr-stack/Vanyshr root.
# Usage: ./workers/fps-playwright/RUN_ON_VPS.sh James Oehring Cameron MO

set -euo pipefail

VPS="vanyshr-vps"
FIRST="${1:-James}"
LAST="${2:-Oehring}"
CITY="${3:-}"
STATE="${4:-}"
OUT="workers/fps-playwright/out"

mkdir -p "$OUT"

echo "→ Copying smoke test to VPS..."
scp workers/fps-playwright/smoke.mjs workers/fps-playwright/package.json "${VPS}:/tmp/"

echo "→ Running on VPS..."
ssh "$VPS" bash -s <<REMOTE || true
  set -euo pipefail
  mkdir -p /tmp/fps-test /tmp/fps-video
  cp /tmp/smoke.mjs /tmp/fps-test/
  cp /tmp/package.json /tmp/fps-test/

  docker run --rm \
    --shm-size=1gb \
    -v /tmp/fps-test:/app \
    -v /tmp:/tmp \
    -w /app \
    mcr.microsoft.com/playwright:v1.61.1-noble \
    bash -c "npm install --silent 2>/dev/null && node smoke.mjs ${FIRST} ${LAST} ${CITY} ${STATE}"
REMOTE

echo ""
echo "→ Pulling outputs..."
scp "${VPS}:/tmp/fps-results.html"   "${OUT}/fps-results.html"   2>/dev/null && echo "  ✓ fps-results.html"   || echo "  - fps-results.html not found"
scp "${VPS}:/tmp/fps-screenshot.png" "${OUT}/fps-screenshot.png" 2>/dev/null && echo "  ✓ fps-screenshot.png" || echo "  - fps-screenshot.png not found"
scp "${VPS}:/tmp/fps-smoke.log"      "${OUT}/fps-smoke.log"      2>/dev/null && echo "  ✓ fps-smoke.log"      || echo "  - fps-smoke.log not found"

VIDEO=$(ssh "$VPS" "ls /tmp/fps-video/*.webm 2>/dev/null | head -1" || true)
if [ -n "$VIDEO" ]; then
  scp "${VPS}:${VIDEO}" "${OUT}/fps-session.webm" && echo "  ✓ fps-session.webm"
else
  echo "  - no video found"
fi

echo ""
echo "→ Done. Open: open ${OUT}/fps-screenshot.png && open ${OUT}/fps-session.webm"
