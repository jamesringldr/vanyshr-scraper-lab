#!/usr/bin/env python3
"""
Quickscan Service — FastAPI wrapper around SequenceRunner.quickscan().

POST /api/quickscan  { first_name, last_name, city?, state? }
  -> 200 SequenceOutput, the raw dataclass shape (dedup_groups / raw_results /
     metadata) -- NOT SequenceOutput.to_dict()'s display shape (profiles).
     Vanyshr-mono's Phase1Orchestrator.tryScraperLab() reads dedup_groups
     directly; the shape matches quickscan-phase1-phase2-models.ts as
     checkpointed on dev/pilot-profile-modal (commit f513db3).

GET  /health  -> { status: "ok" }

Auth: Authorization: Bearer <SCRAPER_LAB_TOKEN>
      (skipped if SCRAPER_LAB_TOKEN unset -- local dev)

Port: 8790  (FPS 8787, Zaba 8788, NPD 8789)

Only wraps quickscan() this pass -- no routes for the FPS-led scan() /
select_profile() flow yet, and no Phase 2 full-profile endpoint. Both are
follow-up passes once this one-shot bridge is proven end to end.
"""
import dataclasses
import logging
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env.local"))

from data_models import QuickScanInput  # noqa: E402
from sequence_runner import SequenceRunner  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("quickscan-service")

SERVICE_TOKEN = os.environ.get("SCRAPER_LAB_TOKEN")
if not SERVICE_TOKEN:
    log.warning("SCRAPER_LAB_TOKEN not set — /api/quickscan accepts unauthenticated requests")

if not os.environ.get("CONTEXT_DEV_API_KEY"):
    log.warning("CONTEXT_DEV_API_KEY not set — every scrape will fail")

app = FastAPI(title="quickscan-service")

_cors = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# One runner reused across requests, same as run_summary_test.py. quickscan()
# resets its own per-call state (_profiles_from_summary) at the start of each
# call, and this endpoint never reads that field back -- only a future
# full-profile endpoint would need per-request isolation.
runner = SequenceRunner()


class QuickscanRequest(BaseModel):
    first_name: str
    last_name: str
    city: Optional[str] = None
    state: Optional[str] = None


def _auth(authorization: Optional[str]):
    if SERVICE_TOKEN and authorization != f"Bearer {SERVICE_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/quickscan")
async def quickscan(req: QuickscanRequest, authorization: Optional[str] = Header(None)):
    _auth(authorization)

    first_name = req.first_name.strip()
    last_name = req.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="first_name and last_name are required")

    log.info("quickscan: %s %s, %s %s", first_name, last_name, req.city, req.state)

    try:
        output = await runner.quickscan(QuickScanInput(
            first_name=first_name,
            last_name=last_name,
            city=(req.city or "").strip(),
            state=(req.state or "").strip(),
        ))
    except Exception as e:
        log.exception("quickscan failed")
        raise HTTPException(status_code=500, detail=str(e))

    # Raw dataclass shape (dedup_groups/raw_results/metadata), not
    # to_dict()'s display shape (profiles) -- see module docstring.
    return JSONResponse(dataclasses.asdict(output))
