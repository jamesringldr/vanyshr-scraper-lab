#!/usr/bin/env bash
# Run the FPS IP-trust baseline probe on the VPS, then pull the CSV.
# Run from the vanyshr-stack/Vanyshr root:
#   ./workers/fps-playwright/RUN_PROBE.sh [N]
#
# Reuses the existing fps-camoufox:latest image (built by RUN_CAMOUFOX_VPS.sh) —
# no rebuild. The probe fetches a FRESH FlameProxies IP per iteration.
#
# Env overrides: FLAMEPROXIES_PACKAGE_ID (default 2549), PROBE_WAIT_S (default 15),
#                FLAMEPROXIES_COUNTRY (default US).

set -euo pipefail

VPS="vanyshr-vps"
N="${1:-100}"
SRC="workers/fps-playwright"
OUT="${SRC}/out"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUNOUT="${OUT}/probe-${STAMP}"
mkdir -p "$RUNOUT"

# ── FlameProxies API key from Bitwarden Secrets Manager ──────────────────────
if [ -z "${FLAMEPROXIES_API_KEY:-}" ]; then
  FLAMEPROXIES_API_KEY=$(bws secret get a6238d1d-c8ec-47b9-915f-b47300586be9 2>/dev/null | jq -r '.value // empty')
fi
if [ -z "${FLAMEPROXIES_API_KEY:-}" ]; then
  echo "ERROR: no FlameProxies API key (BWS). The probe needs proxies to measure IP trust." >&2
  exit 1
fi
FLAMEPROXIES_PACKAGE_ID="${FLAMEPROXIES_PACKAGE_ID:-2549}"
PROBE_WAIT_S="${PROBE_WAIT_S:-15}"
FLAMEPROXIES_COUNTRY="${FLAMEPROXIES_COUNTRY:-US}"

echo "→ Probe: N=${N} pkg=${FLAMEPROXIES_PACKAGE_ID} wait=${PROBE_WAIT_S}s country=${FLAMEPROXIES_COUNTRY}"

echo "→ Copying ip_probe.py to VPS..."
ssh "$VPS" "mkdir -p /tmp/fps-probe /tmp/probe-out"
scp "${SRC}/ip_probe.py" "${VPS}:/tmp/fps-probe/ip_probe.py"

echo "→ Running probe in fps-camoufox:latest (entrypoint overridden)..."
# CB = Playwright's bundled driver JS. It crashes the whole Node process when
# Firefox emits a pageError without a `location` (CF cross-origin iframe errors):
#   url: pageError.location.url  →  TypeError, then ValidationError downstream
# (location.url must be a STRING). We substitute a complete fallback object with
# url=String() ("") so it passes both deref and validation. String() avoids any
# quote chars, keeping the sed safe inside the nested sh -c / heredoc / ssh.
CB="/usr/local/lib/python3.12/dist-packages/playwright/driver/package/lib/coreBundle.js"
PATCH='s/pageError\.location\./(pageError.location||{url:String(),lineNumber:0,columnNumber:0})./g'
ssh "$VPS" bash -s <<REMOTE || true
  set -euo pipefail
  docker run --rm \
    --shm-size=1gb \
    -v /tmp/probe-out:/out \
    -v /tmp/fps-probe/ip_probe.py:/app/ip_probe.py:ro \
    -e OUT_DIR=/out \
    -e FLAMEPROXIES_API_KEY='${FLAMEPROXIES_API_KEY}' \
    -e FLAMEPROXIES_PACKAGE_ID='${FLAMEPROXIES_PACKAGE_ID}' \
    -e FLAMEPROXIES_COUNTRY='${FLAMEPROXIES_COUNTRY}' \
    -e PROBE_WAIT_S='${PROBE_WAIT_S}' \
    --entrypoint sh \
    fps-camoufox:latest -c "sed -i '${PATCH}' '${CB}'; exec python3 /app/ip_probe.py ${N}"
REMOTE

echo ""
echo "→ Pulling results to ${RUNOUT}/ ..."
scp "${VPS}:/tmp/probe-out/ip_baseline.csv" "${RUNOUT}/ip_baseline.csv" 2>/dev/null && echo "  ✓ ip_baseline.csv" || echo "  - ip_baseline.csv missing"
scp "${VPS}:/tmp/probe-out/ip_probe.log"    "${RUNOUT}/ip_probe.log"    2>/dev/null && echo "  ✓ ip_probe.log" || true

echo ""
[ -f "${RUNOUT}/ip_probe.log" ] && { echo "--- baseline summary ---"; tail -15 "${RUNOUT}/ip_probe.log"; }
echo "→ Done. CSV: ${RUNOUT}/ip_baseline.csv"
