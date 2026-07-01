#!/usr/bin/env bash
# Build + run the Camoufox FPS smoke test on the VPS, then pull artifacts.
# Run from the vanyshr-stack/Vanyshr root:
#   ./workers/fps-playwright/RUN_CAMOUFOX_VPS.sh James Oehring Cameron MO
#
# Proxy is auto-fetched from FlameProxies using credentials in workers/fps-playwright/.env
# Override manually: PROXY_SERVER=http://host:port PROXY_USER=u PROXY_PASS=p ./...

set -euo pipefail

VPS="vanyshr-vps"
FIRST="${1:-James}"; LAST="${2:-Oehring}"; CITY="${3:-}"; STATE="${4:-}"
SRC="workers/fps-playwright"
OUT="${SRC}/out"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUNOUT="${OUT}/camoufox-${STAMP}"
mkdir -p "$RUNOUT"

# ── Load FlameProxies API key from Bitwarden Secrets Manager ─────────────────
# BWS UUID: a6238d1d-c8ec-47b9-915f-b47300586be9 (package: premium_residential, ID: 2549)
if [ -z "${FLAMEPROXIES_API_KEY:-}" ]; then
  FLAMEPROXIES_API_KEY=$(bws secret get a6238d1d-c8ec-47b9-915f-b47300586be9 2>/dev/null | jq -r '.value // empty')
  if [ -z "$FLAMEPROXIES_API_KEY" ]; then
    echo "WARNING: could not retrieve FlameProxies API key from BWS — running without proxy"
  fi
fi
FLAMEPROXIES_PACKAGE_ID="${FLAMEPROXIES_PACKAGE_ID:-2549}"

# ── Auto-fetch FlameProxies residential credentials ───────────────────────────
if [ -z "${PROXY_SERVER:-}" ] && [ -n "${FLAMEPROXIES_API_KEY:-}" ]; then
  echo "→ Fetching FlameProxies residential proxy..."
  FP_RESP=$(curl -s -X POST \
    -H "Authorization: Bearer ${FLAMEPROXIES_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"package_id\":${FLAMEPROXIES_PACKAGE_ID:-2549},\"country\":\"US\"}" \
    "https://flameproxies.com/api/customer/proxies/generate")

  # Response: {"proxies":["host:port:user:pass", ...]}
  PROXY_LINE=$(echo "$FP_RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
p = d['proxies'][0]
parts = p.split(':')
print(f'http://{parts[0]}:{parts[1]}')
print(parts[2])
print(parts[3])
" 2>/dev/null)

  if [ -n "$PROXY_LINE" ]; then
    PROXY_SERVER=$(echo "$PROXY_LINE" | sed -n '1p')
    PROXY_USER=$(echo "$PROXY_LINE" | sed -n '2p')
    PROXY_PASS=$(echo "$PROXY_LINE" | sed -n '3p')
    echo "  proxy: ${PROXY_SERVER} user=${PROXY_USER}"
  else
    echo "  WARNING: failed to parse FlameProxies response: ${FP_RESP}"
  fi
fi

# ── Build proxy env flags for docker run ─────────────────────────────────────
PROXY_ENV=""
[ -n "${PROXY_SERVER:-}" ] && PROXY_ENV="$PROXY_ENV -e PROXY_SERVER=${PROXY_SERVER}"
[ -n "${PROXY_USER:-}" ]   && PROXY_ENV="$PROXY_ENV -e PROXY_USER=${PROXY_USER}"
[ -n "${PROXY_PASS:-}" ]   && PROXY_ENV="$PROXY_ENV -e PROXY_PASS=${PROXY_PASS}"

# Fingerprint flag: NATIVE_FP=1 drops the os=["windows"] spoof so Camoufox uses
# the host OS — on the VPS that means native Linux. Mirror the local win's one-
# variable change. Unset = Windows spoof (the prior VPS config).
NATIVE_ENV=""
[ "${NATIVE_FP:-}" = "1" ] && NATIVE_ENV="-e NATIVE_FP=1"

echo "→ Copying build context to VPS..."
ssh "$VPS" "mkdir -p /tmp/fps-camoufox"
scp "${SRC}/smoke.py" "${SRC}/Dockerfile.camoufox" "${VPS}:/tmp/fps-camoufox/"

echo "→ Building image + running on VPS (first build downloads Camoufox, ~minutes)..."
ssh "$VPS" bash -s <<REMOTE || true
  set -euo pipefail
  cd /tmp/fps-camoufox
  # Remove previous output as root (docker writes video as root, can't rm as deploy)
  docker run --rm -v /tmp/fps-out:/out --entrypoint sh fps-camoufox:latest -c "rm -rf /out/*" 2>/dev/null || rm -rf /tmp/fps-out
  mkdir -p /tmp/fps-out
  docker build -f Dockerfile.camoufox -t fps-camoufox:latest .
  # Patch Playwright's bundled driver JS: it crashes the whole Node process when
  # Firefox emits a pageError without a location (CF cross-origin iframe errors) —
  # exactly what the CF challenge page triggers. String() fallback gives a valid "".
  CB="/usr/local/lib/python3.12/dist-packages/playwright/driver/package/lib/coreBundle.js"
  docker run --rm \
    --shm-size=1gb \
    -v /tmp/fps-out:/out \
    ${PROXY_ENV} \
    ${NATIVE_ENV} \
    --entrypoint sh \
    fps-camoufox:latest -c "sed -i 's/pageError\.location\./(pageError.location||{url:String(),lineNumber:0,columnNumber:0})./g' '\$CB'; exec python3 /app/smoke.py '${FIRST}' '${LAST}' '${CITY}' '${STATE}'"
REMOTE

echo ""
echo "→ Pulling artifacts to ${RUNOUT}/ ..."
for f in fps-smoke.log fps-results.html fps-screenshot.png fps-error.html \
         google-captcha.html google-results.html \
         recaptcha-before.png recaptcha-after.png \
         turnstile-failed.png; do
  scp "${VPS}:/tmp/fps-out/${f}" "${RUNOUT}/${f}" 2>/dev/null && echo "  ✓ ${f}" || true
done
scp "${VPS}:/tmp/fps-out/fps-session.mp4" "${RUNOUT}/fps-session.mp4" 2>/dev/null && echo "  ✓ fps-session.mp4" || echo "  - fps-session.mp4 not found"

echo ""
echo "→ Done. Artifacts in ${RUNOUT}/"
echo "   open ${RUNOUT}/fps-screenshot.png ; open ${RUNOUT}/fps-session.mp4"
[ -f "${RUNOUT}/fps-smoke.log" ] && { echo "--- log tail ---"; tail -25 "${RUNOUT}/fps-smoke.log"; }
