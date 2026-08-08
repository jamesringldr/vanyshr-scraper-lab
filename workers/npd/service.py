#!/usr/bin/env python3
"""
NPD Scraper Service — FastAPI wrapper around npd_scraper.py.

POST /v1/npd/search  { first_name, last_name, city?, state? }
  -> 200 { status, profiles, count, elapsed_ms, ... }

GET  /health  -> { status: "ok" }

Auth: Authorization: Bearer <NPD_SERVICE_TOKEN>
      (skipped if NPD_SERVICE_TOKEN unset — local dev)

Port: 8789  (FPS 8787, Zaba 8788)
"""
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


def _load_dotenv():
    here = Path(__file__).resolve().parent
    candidates = [here / ".env", here / ".env.txt"]
    envf = next((p for p in candidates if p.exists()), None)
    if not envf:
        print(f"npd-service: no .env found in {here}")
        return
    print(f"npd-service: loading env from {envf}")
    text = envf.read_text(encoding="utf-8-sig")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k:
            os.environ.setdefault(k, v)


_load_dotenv()

import npd_scraper  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("npd-service")

SERVICE_TOKEN = os.environ.get("NPD_SERVICE_TOKEN")

if not SERVICE_TOKEN:
    log.warning("NPD_SERVICE_TOKEN not set — /v1/npd/search accepts unauthenticated requests")
else:
    log.info("NPD_SERVICE_TOKEN loaded (%d chars)", len(SERVICE_TOKEN))

log.info(
    "NPD_USE_FLAME=%s FLAMEPROXIES_API_KEY=%s",
    os.environ.get("NPD_USE_FLAME", ""),
    "set" if os.environ.get("FLAMEPROXIES_API_KEY") else "MISSING",
)

app = FastAPI(title="npd-scraper-service")

_cors = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
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


@app.post("/v1/npd/search")
async def search(req: SearchRequest, authorization: Optional[str] = Header(None)):
    _auth(authorization)

    first_name = req.first_name.strip()
    last_name = req.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="first_name and last_name are required")

    log.info("Search: %s %s, %s %s", first_name, last_name, req.city, req.state)

    result = await npd_scraper.search(
        first_name,
        last_name,
        (req.city or "").strip() or None,
        (req.state or "").strip() or None,
    )
    return JSONResponse(result)
