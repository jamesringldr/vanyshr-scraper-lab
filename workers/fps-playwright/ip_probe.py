#!/usr/bin/env python3
"""
FPS IP-trust baseline probe.

Purpose: measure how Cloudflare *scores the IP* on fastpeoplesearch.com,
isolated from our click/solver bug. Each iteration pulls a FRESH proxy IP
(rotate-per-request), loads FPS with a Google referer, watches CF's challenge
telemetry, and classifies the IP — WITHOUT ever trying to click Turnstile.

Verdict (the tri-state from our analysis):
  GREEN     - no challenge issued. CF trusts the IP outright.
  YELLOW    - challenge issued, last challenges.cloudflare.com flow/ov1 == 200.
              CF would accept a human click → IP is workable; any failure here
              is OUR solver bug, not the IP.
  RED       - challenge issued, last flow/ov1 == 400. CF rejected the IP.
  AMBIGUOUS - challenged but no decisive flow/ov1 seen in the wait window.
  ERROR     - proxy fetch / navigation failed (not an IP-trust signal).

CRITICAL: the browser config here is byte-identical to smoke.py (headless=False
+ Xvfb, same firefox_user_prefs, geoip=False) so the baseline transfers to prod.
We only strip Google/clicking/form/video — keep the fingerprint identical.

Usage:  python3 ip_probe.py [N]          (default N=100)
Env:    FLAMEPROXIES_API_KEY  (required)  FLAMEPROXIES_PACKAGE_ID (default 2549)
        PROBE_WAIT_S (default 15)  OUT_DIR (default /out)
Output: $OUT_DIR/ip_baseline.csv  (+ ip_probe.log)
"""

import os
import re
import sys
import csv
import json
import time
import random
import signal
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from camoufox.sync_api import Camoufox

N = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PROBE_N", "100"))
WAIT_S = float(os.environ.get("PROBE_WAIT_S", "15"))
COUNTRY = os.environ.get("FLAMEPROXIES_COUNTRY", "US")
API_KEY = os.environ.get("FLAMEPROXIES_API_KEY", "")
PACKAGE_ID = int(os.environ.get("FLAMEPROXIES_PACKAGE_ID", "2549"))

OUT_DIR = Path(os.environ.get("OUT_DIR", "/out"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = OUT_DIR / "ip_baseline.csv"
LOG_PATH = OUT_DIR / "ip_probe.log"

FPS_URL = "https://www.fastpeoplesearch.com/"
REFERER = "https://www.google.com/search?q=fast+people+search"

LOG = []


def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    LOG.append(line)
    LOG_PATH.write_text("\n".join(LOG))


def sleep(ms):
    time.sleep(ms / 1000.0)


# ─── Xvfb (headless=False needs a real display; no ffmpeg — we don't record) ──

DISPLAY = ":99"
_xvfb = None


def start_display():
    global _xvfb
    _xvfb = subprocess.Popen(
        ["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = DISPLAY
    time.sleep(1.0)


def stop_display():
    if _xvfb:
        try:
            _xvfb.terminate(); _xvfb.wait(timeout=5)
        except Exception:
            _xvfb.kill()


# ─── FlameProxies: fetch one fresh rotating IP ────────────────────────────────

def fetch_proxy():
    """Return {server,username,password} for a fresh FlameProxies IP, or None."""
    if not API_KEY:
        return None
    body = json.dumps({"package_id": PACKAGE_ID, "country": COUNTRY}).encode()
    req = urllib.request.Request(
        "https://flameproxies.com/api/customer/proxies/generate",
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            # FlameProxies' API WAF 403s the default Python-urllib UA — spoof curl.
            "User-Agent": "curl/8.4.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        host, port, user, pw = data["proxies"][0].split(":")
        return {"server": f"http://{host}:{port}", "username": user, "password": pw}
    except Exception as e:
        log(f"  proxy fetch failed: {e}")
        return None


# ─── Camoufox config — IDENTICAL to smoke.py (do not diverge) ─────────────────

def cam_kwargs(proxy):
    kw = dict(
        headless=False,
        humanize=True,
        os=["windows"],
        geoip=False,
        firefox_user_prefs={
            "privacy.trackingprotection.enabled": False,
            "privacy.trackingprotection.pbmode.enabled": False,
            "privacy.firstparty.isolate": False,
            "privacy.partition.network_state.connection_with_proxy": False,
            "network.http.referer.disallowCrossSiteRelaxingDefault": False,
        },
    )
    if proxy:
        kw["proxy"] = proxy
    return kw


# ─── One probe ────────────────────────────────────────────────────────────────

def probe_once(idx):
    """Run a single IP probe. Returns a CSV-row dict."""
    t0 = time.time()
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "idx": idx,
        "egress_ip": "",
        "verdict": "ERROR",
        "challenged": "",
        "cf_flow_ov1_last": "",
        "cf_chl_cleared": "",
        "initial_status": "",
        "title": "",
        "elapsed_s": "",
        "note": "",
    }

    proxy = fetch_proxy()
    if API_KEY and not proxy:
        row["note"] = "proxy_fetch_failed"
        row["elapsed_s"] = f"{time.time() - t0:.1f}"
        return row

    # CF telemetry captured via response listener
    state = {"ov1_last": None, "challenged": False, "initial_status": None}

    try:
        with Camoufox(**cam_kwargs(proxy)) as browser:
            ctx = browser.new_context()
            page = ctx.new_page()
            page.add_init_script("window.onerror = function() { return true; };")

            def on_resp(r):
                u = r.url
                # The decisive IP-score signal lives on challenges.cloudflare.com
                if "challenges.cloudflare.com" in u and "/flow/ov1/" in u:
                    state["ov1_last"] = r.status
                if "fastpeoplesearch.com/" in u and u.rstrip("/").endswith("fastpeoplesearch.com"):
                    if state["initial_status"] is None:
                        state["initial_status"] = r.status
            page.on("response", on_resp)

            # Egress IP (confirms proxy routing + gives us the IP to dedupe on).
            # ipify is flaky through some residential exits — fall back across a
            # couple of echo services so we capture the IP label more often. This
            # is best-effort: a miss costs only the dedup label, not the verdict.
            if proxy:
                for echo in ("https://api.ipify.org?format=text",
                             "https://icanhazip.com",
                             "https://ifconfig.me/ip"):
                    try:
                        page.goto(echo, wait_until="domcontentloaded", timeout=10000)
                        body = page.inner_text("body").strip().splitlines()
                        m = re.match(r"^\d{1,3}(\.\d{1,3}){3}$", body[0].strip()) if body else None
                        if m:
                            row["egress_ip"] = body[0].strip()
                            break
                    except Exception as e:
                        row["note"] = f"egress_check_failed:{e!s:.30}"

            # The actual probe: FPS with Google referer (same path as prod)
            nav_ok = True
            proxy_dead = False
            try:
                page.goto(FPS_URL, referer=REFERER,
                          wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                nav_ok = False
                es = str(e)
                if "PROXY" in es or "BAD_GATEWAY" in es or "NS_ERROR_PROXY" in es:
                    proxy_dead = True
                row["note"] = (row["note"] + f"|goto_failed:{es:.40}").strip("|")

            row["initial_status"] = state["initial_status"] or ""
            url = page.url
            title = ""
            try:
                title = page.title()
            except Exception:
                pass

            challenged = ("__cf_chl_rt_tk" in url
                          or "just a moment" in title.lower()
                          or state["initial_status"] == 403)

            # Let CF run its automated checks; watch for ov1 verdict / auto-clear
            deadline = time.time() + WAIT_S
            cleared = False
            while time.time() < deadline:
                sleep(1500 + random.random() * 500)
                try:
                    cur = page.url
                    cur_title = (page.title() or "").lower()
                except Exception:
                    break
                if "__cf_chl_rt_tk" in cur:
                    challenged = True
                if challenged and "__cf_chl_rt_tk" not in cur and "just a moment" not in cur_title:
                    cleared = True
                # Once CF has emitted a decisive ov1, we have our signal
                if state["ov1_last"] in (200, 400):
                    pass  # keep watching briefly in case it flips, but it's recorded

            state["challenged"] = challenged
            row["challenged"] = "yes" if challenged else "no"
            row["cf_flow_ov1_last"] = state["ov1_last"] if state["ov1_last"] is not None else ""
            row["cf_chl_cleared"] = "yes" if cleared else "no"
            row["title"] = title[:40]

            # ── Classify ──
            # GREEN requires POSITIVE evidence of a real FPS load — not merely the
            # absence of a challenge. A dead proxy / nav timeout shows no challenge
            # AND no content; that's infra noise (ERROR), not a trusted IP. Counting
            # it GREEN would inflate the baseline.
            fps_loaded = ("people search" in (title or "").lower()
                          or state["initial_status"] in (200, 301, 302))
            if proxy_dead or (not nav_ok and not challenged):
                row["verdict"] = "ERROR"
                if not row["note"]:
                    row["note"] = "nav_failed"
            elif not challenged:
                row["verdict"] = "GREEN" if fps_loaded else "AMBIGUOUS"
            elif state["ov1_last"] == 200:
                row["verdict"] = "YELLOW"
            elif state["ov1_last"] == 400:
                row["verdict"] = "RED"
            else:
                row["verdict"] = "AMBIGUOUS"

            ctx.close()
    except Exception as e:
        row["note"] = (row["note"] + f"|browser_err:{e!s:.60}").strip("|")
        row["verdict"] = "ERROR"

    row["elapsed_s"] = f"{time.time() - t0:.1f}"
    return row


def main():
    log(f"IP probe — N={N} wait={WAIT_S}s country={COUNTRY} pkg={PACKAGE_ID} "
        f"proxy={'yes' if API_KEY else 'NONE'}")
    start_display()

    fields = ["ts", "idx", "egress_ip", "verdict", "challenged",
              "cf_flow_ov1_last", "cf_chl_cleared", "initial_status",
              "title", "elapsed_s", "note"]
    new_file = not CSV_PATH.exists()
    f = CSV_PATH.open("a", newline="")
    w = csv.DictWriter(f, fieldnames=fields)
    if new_file:
        w.writeheader()

    tally = {"GREEN": 0, "YELLOW": 0, "RED": 0, "AMBIGUOUS": 0, "ERROR": 0}
    seen_ips = set()

    try:
        for i in range(1, N + 1):
            row = probe_once(i)
            w.writerow(row); f.flush()
            tally[row["verdict"]] = tally.get(row["verdict"], 0) + 1
            if row["egress_ip"]:
                seen_ips.add(row["egress_ip"])
            log(f"  [{i}/{N}] ip={row['egress_ip'] or '?':<15} "
                f"{row['verdict']:<9} ov1={row['cf_flow_ov1_last'] or '-'} "
                f"cleared={row['cf_chl_cleared'] or '-'} {row['elapsed_s']}s "
                f"{row['note']}")
            sleep(800 + random.random() * 700)  # jitter between proxy fetches
    finally:
        f.close()
        stop_display()

    total = sum(tally.values())
    workable = tally["GREEN"] + tally["YELLOW"]
    log("")
    log("━━━━━━━━━━━━━━━ IP BASELINE ━━━━━━━━━━━━━━━")
    log(f"  total probes:    {total}")
    log(f"  distinct IPs:    {len(seen_ips)}  (true sample size)")
    log(f"  GREEN  (trusted):   {tally['GREEN']}")
    log(f"  YELLOW (workable):  {tally['YELLOW']}")
    log(f"  RED    (rejected):  {tally['RED']}")
    log(f"  AMBIGUOUS:          {tally['AMBIGUOUS']}")
    log(f"  ERROR (excl.):      {tally['ERROR']}")
    scorable = total - tally["ERROR"]
    if scorable:
        log(f"  → IP-not-the-blocker rate (GREEN+YELLOW): "
            f"{workable}/{scorable} = {100*workable/scorable:.0f}%")
    log(f"  CSV: {CSV_PATH}")
    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    def _sigterm(*_):
        stop_display(); sys.exit(1)
    signal.signal(signal.SIGTERM, _sigterm)
    main()
