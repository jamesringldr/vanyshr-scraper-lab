#!/usr/bin/env python3
"""HTTP service wrapping the FPS Camoufox + curl_cffi pipeline (fps_pipeline.py)
for synchronous calls from a Supabase edge function during a live QuickScan.

POST /v1/fps/search   { first_name, last_name, city?, state? }
  -> 200 { status: "success", ...QuickScanProfileData fields }
  -> 200 { status: "blocked" | "no_results" | "failed", error? }

Auth: Authorization: Bearer <FPS_SERVICE_TOKEN> (skipped if that env var is unset,
e.g. for local dev).

Runs are serialized behind SEARCH_LOCK: each run launches a real Firefox
(Camoufox) on this box's single residential IP/identity, and cf_clearance is
IP-locked and short-lived, so overlapping runs would fight over the same
session rather than speeding anything up. Requests queue instead of running in
parallel.
"""
import asyncio
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import fps_pipeline as pipeline

SCRIPT_DIR = Path(__file__).parent


def _load_dotenv():
    envf = SCRIPT_DIR / ".env"
    if not envf.exists():
        return
    for line in envf.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fps-service")

SERVICE_TOKEN = os.environ.get("FPS_SERVICE_TOKEN")
SMOKE_TIMEOUT_S = int(os.environ.get("FPS_SMOKE_TIMEOUT_S", "120"))
KEEP_ARTIFACTS = os.environ.get("FPS_KEEP_ARTIFACTS") == "1"

if not SERVICE_TOKEN:
    log.warning("FPS_SERVICE_TOKEN not set — /v1/fps/search will accept unauthenticated requests")

SEARCH_LOCK = asyncio.Lock()

app = FastAPI(title="fps-scraper-service")


class SearchRequest(BaseModel):
    first_name: str
    last_name: str
    city: Optional[str] = None
    state: Optional[str] = None


# smoke.py classify() outcomes (plus its early-return labels) that mean the
# Turnstile/Cloudflare challenge did not clear or navigation didn't reach FPS.
BLOCKED_CLASSIFICATIONS = {"blocked", "turnstile", "fps_home", "unknown", "no_fps_links"}


def _classify_smoke_result(classification: str) -> str:
    if classification == "success":
        return "success"
    if classification == "no_results":
        return "no_results"
    if classification in BLOCKED_CLASSIFICATIONS or classification.startswith("google_recaptcha_"):
        return "blocked"
    return "failed"  # "error" or anything unrecognized


def _run_pipeline_sync(first_name: str, last_name: str, city: Optional[str],
                        state: Optional[str]) -> dict:
    run_dir = Path(tempfile.mkdtemp(prefix="fps-run-"))
    t0 = time.monotonic()
    try:
        try:
            classification, log_tail = pipeline.run_smoke(
                first_name, last_name, city or "", state or "",
                run_dir, timeout_s=SMOKE_TIMEOUT_S,
            )
        except pipeline.SmokeTimeout as e:
            return {"status": "failed", "error": str(e)}

        outcome = _classify_smoke_result(classification)
        log.info("smoke classification=%s -> outcome=%s (%.1fs)",
                  classification, outcome, time.monotonic() - t0)

        if outcome == "no_results":
            return {"status": "no_results"}
        if outcome == "blocked":
            return {"status": "blocked", "error": f"smoke classification: {classification}"}
        if outcome == "failed":
            return {"status": "failed", "error": f"smoke classification: {classification}\n{log_tail}"}

        # outcome == "success" -> Turnstile cleared, cf_clearance harvested.
        if not (run_dir / "cf_cookies.json").exists():
            return {"status": "failed", "error": "smoke reported success but wrote no cf_cookies.json"}

        fetch = pipeline.fetch_detail_via_cffi(run_dir, first_name, last_name, city, state)
        if fetch["status"] == "no_results":
            return {"status": "no_results"}
        if fetch["status"] == "blocked":
            return {"status": "blocked", "error": "curl_cffi replay did not clear Cloudflare"}

        profile = pipeline.build_profile(
            fetch["detail_html"], fetch["detail_url"], first_name, last_name,
        )
        return {"status": "success", **profile}

    except Exception as e:
        log.exception("pipeline error")
        return {"status": "failed", "error": str(e)}
    finally:
        if not KEEP_ARTIFACTS:
            shutil.rmtree(run_dir, ignore_errors=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/fps/search")
async def search(req: SearchRequest, authorization: Optional[str] = Header(None)):
    if SERVICE_TOKEN and authorization != f"Bearer {SERVICE_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

    first_name = req.first_name.strip()
    last_name = req.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="first_name and last_name are required")

    async with SEARCH_LOCK:
        result = await asyncio.to_thread(
            _run_pipeline_sync, first_name, last_name,
            (req.city or "").strip() or None, (req.state or "").strip() or None,
        )

    return JSONResponse(result)
