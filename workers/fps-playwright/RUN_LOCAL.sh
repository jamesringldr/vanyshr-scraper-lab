#!/usr/bin/env bash
# Run the FPS smoke test LOCALLY on your Mac, headed, so you can watch live.
# Isolation ladder for "is it the VPS environment or the code?":
#   RUNG 1 (default): direct on your ISP, no proxy.
#       ./workers/fps-playwright/RUN_LOCAL.sh James Oehring Cameron MO
#   RUNG 2: same, but through FlameProxies (rule the proxy in/out):
#       USE_FLAME=1 ./workers/fps-playwright/RUN_LOCAL.sh James Oehring Cameron MO
#
# Uses the isolated venv at workers/fps-playwright/.venv-local (Camoufox installed).
# Browser config is byte-identical to the VPS run; only Xvfb/ffmpeg are skipped
# (Linux-only) via LOCAL_HEADED=1. A real Firefox window opens — watch it.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIRST="${1:-James}"; LAST="${2:-Oehring}"; CITY="${3:-Cameron}"; STATE="${4:-MO}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUNOUT="${SRC}/out/local-${STAMP}"
mkdir -p "$RUNOUT"

if [ ! -d "${SRC}/.venv-local" ]; then
  echo "ERROR: ${SRC}/.venv-local missing. Install first:" >&2
  echo "  python3 -m venv ${SRC}/.venv-local && . ${SRC}/.venv-local/bin/activate && pip install 'camoufox[geoip]' && python -m camoufox fetch" >&2
  exit 1
fi
# shellcheck disable=SC1091
. "${SRC}/.venv-local/bin/activate"

export LOCAL_HEADED=1
export OUT_DIR="$RUNOUT"

# ── RUNG 2: optionally route through FlameProxies (fetched locally) ───────────
if [ "${USE_FLAME:-0}" = "1" ]; then
  if [ -z "${FLAMEPROXIES_API_KEY:-}" ]; then
    FLAMEPROXIES_API_KEY=$(bws secret get a6238d1d-c8ec-47b9-915f-b47300586be9 2>/dev/null | jq -r '.value // empty')
  fi
  FLAMEPROXIES_PACKAGE_ID="${FLAMEPROXIES_PACKAGE_ID:-2549}"
  echo "→ RUNG 2: fetching FlameProxies proxy..."
  FP_RESP=$(curl -s -X POST -H "Authorization: Bearer ${FLAMEPROXIES_API_KEY}" \
    -H "Content-Type: application/json" -H "User-Agent: curl/8.4.0" \
    -d "{\"package_id\":${FLAMEPROXIES_PACKAGE_ID},\"country\":\"US\"}" \
    "https://flameproxies.com/api/customer/proxies/generate")
  read -r PROXY_SERVER PROXY_USER PROXY_PASS < <(echo "$FP_RESP" | python3 -c "
import sys,json
p=json.load(sys.stdin)['proxies'][0].split(':')
print(f'http://{p[0]}:{p[1]}', p[2], p[3])")
  export PROXY_SERVER PROXY_USER PROXY_PASS
  echo "  proxy: ${PROXY_SERVER} user=${PROXY_USER}"
else
  echo "→ RUNG 1: direct on your ISP (no proxy)"
fi

echo "→ Output: ${RUNOUT}"
echo "→ A Firefox window will open — watch the Google → FPS flow live."
echo

python "${SRC}/smoke.py" "$FIRST" "$LAST" "$CITY" "$STATE" || true

echo
echo "→ Done. Classification:"; grep -E "Classification:|DONE:" "${RUNOUT}/fps-smoke.log" 2>/dev/null | tail -2
echo "→ Artifacts: ${RUNOUT}/  (fps-screenshot.png, fps-results.html, fps-smoke.log)"
