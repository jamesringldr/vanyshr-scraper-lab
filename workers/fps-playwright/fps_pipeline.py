#!/usr/bin/env python3
"""Callable wrapper around the validated FPS pipeline (smoke.py Camoufox harvest
-> curl_cffi replay -> parse_detail.py), parameterized for service.py instead of
the hardcoded/CLI scripts. Mirrors fetch_flow.py's request shape exactly (same
impersonate target, same header set) since that's the config already proven to
work against a live cf_clearance harvest."""
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from curl_cffi import requests as cffi_requests

import parse_detail

SCRIPT_DIR = Path(__file__).parent
SMOKE_PY = SCRIPT_DIR / "smoke.py"

# classify()'s own markers, mirrored here for the curl_cffi-fetched pages (which
# never go through smoke.py's classify()).
CF_CHALLENGE_MARKERS = (
    "just a moment", "checking your browser", "access denied",
    "security challenge", "cf-mitigated", "/cdn-cgi/challenge-platform",
)
NO_RESULTS_MARKERS = ("did not return any matches", "no results found")

# smoke.py's log() prefixes every line with an ISO timestamp, e.g.
# "[2026-07-02T05:12:33+00:00] DONE: success" — match the marker, not line-start.
DONE_RE = re.compile(r"\bDONE:\s*(\S+)")


class SmokeTimeout(Exception):
    pass


def run_smoke(first: str, last: str, city: str, state: str, out_dir: Path,
              timeout_s: int = 120) -> tuple:
    """Runs smoke.py (Camoufox: solves Turnstile, harvests cf_clearance into
    out_dir/cf_cookies.json) as a subprocess. Returns (classification, log_tail).
    Uses the same Python interpreter running this service, so it shares the venv
    (camoufox etc. must be installed there). Raises SmokeTimeout on timeout."""
    env = {**os.environ, "OUT_DIR": str(out_dir), "SKIP_GOOGLE": "1"}
    # Xvfb/ffmpeg (smoke.py's headless-recording path) are Linux-only. On
    # Windows/macOS, LOCAL_HEADED=1 is required — Camoufox renders into the
    # real (interactive) desktop session instead. Matches serv-01's own
    # run_direct.bat, which is the proven-working invocation on that box.
    if not sys.platform.startswith("linux"):
        env["LOCAL_HEADED"] = "1"
    args = [sys.executable, str(SMOKE_PY), first, last, city or "", state or ""]

    is_windows = os.name == "nt"
    popen_kwargs = {}
    if is_windows:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # smoke.py spawns Xvfb/ffmpeg/Firefox as its own children. A plain
        # timeout kill only reaps smoke.py itself and orphans the rest — start
        # it in its own process group so a timeout can take the whole tree
        # down with it.
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        args, cwd=str(SCRIPT_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        **popen_kwargs,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        if is_windows:
            # taskkill /T kills the whole process tree (Firefox etc.), not just smoke.py.
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            capture_output=True)
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.communicate()
        raise SmokeTimeout(f"smoke.py exceeded {timeout_s}s")

    stdout = stdout or ""
    # Captured pipe stdout has proven unreliable when smoke.py is launched from
    # a Scheduled-Task-spawned interactive session on Windows (observed: full
    # successful runs, verified via smoke.py's own fps-smoke.log, with an
    # empty captured pipe). smoke.py writes that log itself (flush_log()) once
    # it finishes, so prefer it as the authoritative source and only fall back
    # to the captured pipe if the file isn't there (e.g. a crash before it
    # could be written).
    log_file = out_dir / "fps-smoke.log"
    source = stdout
    if log_file.exists():
        try:
            source = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    m = DONE_RE.search(source)
    classification = m.group(1) if m else "error"
    tail = "\n".join(source.splitlines()[-20:] + (stderr or "").splitlines()[-10:])
    return classification, tail


def _looks_blocked(html: str) -> bool:
    lc = html.lower()
    return len(html) < 8000 and any(marker in lc for marker in CF_CHALLENGE_MARKERS)


def _looks_no_results(html: str) -> bool:
    lc = html.lower()
    return any(marker in lc for marker in NO_RESULTS_MARKERS)


def _slug(first: str, last: str, city: Optional[str], state: Optional[str]) -> str:
    name = f"{first}-{last}".lower().replace(" ", "-")
    loc_parts = [p for p in (city, state) if p]
    if not loc_parts:
        return name
    loc = "-".join(loc_parts).lower().replace(" ", "-")
    return f"{name}_{loc}"


def fetch_detail_via_cffi(out_dir: Path, first: str, last: str,
                           city: Optional[str], state: Optional[str]) -> dict:
    """Replays the cf_clearance harvested by run_smoke() via curl_cffi (Firefox135
    JA3 impersonation) — same box, same egress IP, run immediately after the
    Camoufox mint so the ~15min/IP-locked cookie is still fresh. Fetches the
    summary page, finds the top match's _id_ detail link, fetches the detail
    page. Returns {"status": "success", "detail_html", "detail_url"} or
    {"status": "no_results"} or {"status": "blocked"}."""
    ck = json.loads((out_dir / "cf_cookies.json").read_text())
    cookies = {c["name"]: c["value"] for c in ck["cookies"]}
    ua = ck["ua"]
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
    }

    summary_url = f"https://www.fastpeoplesearch.com/name/{_slug(first, last, city, state)}"
    s = cffi_requests.get(summary_url, cookies=cookies, headers=headers,
                           impersonate="firefox135", timeout=30)
    if _looks_blocked(s.text):
        return {"status": "blocked"}
    if _looks_no_results(s.text):
        return {"status": "no_results"}

    m = re.search(r'href="(/[a-z0-9-]+_id_[A-Za-z0-9-]+)"', s.text, re.I)
    if not m:
        return {"status": "no_results"}

    detail_url = "https://www.fastpeoplesearch.com" + m.group(1)
    d = cffi_requests.get(detail_url, cookies=cookies,
                           headers={**headers, "Referer": summary_url},
                           impersonate="firefox135", timeout=30)
    if _looks_blocked(d.text):
        return {"status": "blocked"}

    return {"status": "success", "detail_html": d.text, "detail_url": detail_url}


def build_profile(detail_html: str, detail_url: str, first_name: str,
                   last_name: str) -> dict:
    """Maps parse_detail.py's output onto QuickScanProfileData
    (supabase/functions/_shared/scrapers/BaseScraper.ts)."""
    parsed = parse_detail.parse(detail_html)

    addresses = []
    cur = parsed.get("current_address") or {}
    if cur:
        estimated_value = cur.get("estimated_value")
        addresses.append({
            "full_address": cur.get("full"),
            "county": cur.get("county"),
            "is_current": True,
            "years_lived": cur.get("since"),
            "property_type": cur.get("property"),
            "property": {"estimated_value": estimated_value} if estimated_value else None,
        })
    for prev in parsed.get("previous_addresses") or []:
        addresses.append({"full_address": prev, "is_current": False})

    phones = [
        {
            "number": p.get("number"),
            "type": p.get("type"),
            "provider": p.get("carrier"),
            "first_reported": p.get("first_reported"),
        }
        for p in parsed.get("phones") or [] if p.get("number")
    ]

    emails = [{"email": e} for e in parsed.get("emails") or []]

    relatives = [
        {
            "name": r.get("name"),
            "age": str(r["age"]) if r.get("age") is not None else None,
        }
        for r in parsed.get("relatives") or [] if r.get("name")
    ]

    age = parsed.get("age")

    return {
        "name": parsed.get("name") or f"{first_name} {last_name}",
        "first_name": first_name,
        "last_name": last_name,
        "age": str(age) if age is not None else None,
        "phones": phones,
        "emails": emails,
        "addresses": addresses,
        "relatives": relatives,
        "aliases": [],
        "jobs": [],
        "education": [],
        "social_profiles": [],
        "legal_records": [],
        "background_records": [],
        "assets": [],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "sources": ["FastPeopleSearch"],
        "detail_link": detail_url,
    }
