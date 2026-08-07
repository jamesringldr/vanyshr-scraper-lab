#!/usr/bin/env python3
"""
Zaba Scraper Service — FastAPI wrapper around zaba_scraper.py.

POST /v1/zaba/search  { first_name, last_name, city?, state? }
  -> 200 { status: "success", profiles: [...], count: N, elapsed_ms: N }
  -> 200 { status: "no_results", profiles: [], count: 0, elapsed_ms: N }
  -> 200 { status: "failed", error: "...", elapsed_ms: N }

GET  /health  -> { status: "ok" }

Auth: Authorization: Bearer <ZABA_SERVICE_TOKEN>
      (skipped if ZABA_SERVICE_TOKEN env var is unset — e.g. local dev)

Unlike FPS, Zaba requests are pure HTTP — no browser, no lock.
Concurrent requests are fine; each gets its own FlameProxies credential.

Port: 8788  (FPS is 8787)
"""
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Env MUST load before importing zaba_scraper (it reads env at import) ───────

def _load_dotenv():
    """Load KEY=value from .env next to this file. Also accepts .env.txt (Windows Save As trap)."""
    here = Path(__file__).resolve().parent
    candidates = [here / ".env", here / ".env.txt"]
    envf = next((p for p in candidates if p.exists()), None)
    if not envf:
        print(f"zaba-service: no .env found in {here} (looked for .env and .env.txt)")
        return
    print(f"zaba-service: loading env from {envf}")
    text = envf.read_text(encoding="utf-8-sig")  # utf-8-sig strips Windows BOM
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k:
            os.environ.setdefault(k, v)

_load_dotenv()

import zaba_scraper  # noqa: E402  — after env load on purpose

# ── App ────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("zaba-service")

SERVICE_TOKEN = os.environ.get("ZABA_SERVICE_TOKEN")

if not SERVICE_TOKEN:
    log.warning("ZABA_SERVICE_TOKEN not set — /v1/zaba/search will accept unauthenticated requests")
else:
    log.info("ZABA_SERVICE_TOKEN loaded (%d chars)", len(SERVICE_TOKEN))

log.info(
    "ZABA_DIRECT_FALLBACK=%s FLAMEPROXIES_API_KEY=%s",
    os.environ.get("ZABA_DIRECT_FALLBACK", ""),
    "set" if os.environ.get("FLAMEPROXIES_API_KEY") else "MISSING",
)

app = FastAPI(title="zaba-scraper-service")

# Browser / admin UI may call this the same way as FPS once a hostname is reachable.
# Restrict via CORS_ORIGINS env (comma-separated); default * for Tailscale lab only.
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


class FetchUrlRequest(BaseModel):
    url: str


def _auth(authorization: Optional[str]):
    if SERVICE_TOKEN and authorization != f"Bearer {SERVICE_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/zaba/search")
async def search(req: SearchRequest, authorization: Optional[str] = Header(None)):
    """Full search + parse — returns structured profile data."""
    _auth(authorization)

    first_name = req.first_name.strip()
    last_name  = req.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="first_name and last_name are required")

    log.info("Search: %s %s, %s %s", first_name, last_name, req.city, req.state)

    result = await zaba_scraper.search(
        first_name,
        last_name,
        (req.city or "").strip() or None,
        (req.state or "").strip() or None,
    )

    return JSONResponse(result)


@app.post("/v1/zaba/fetch-url")
async def fetch_url(req: FetchUrlRequest, authorization: Optional[str] = Header(None)):
    """Fetch raw HTML through Flame — for ops/debug only (not used by edge)."""
    _auth(authorization)

    if not req.url.startswith("https://www.zabasearch.com/"):
        raise HTTPException(status_code=400, detail="url must be a zabasearch.com URL")

    log.info("fetch-url: %s", req.url)
    html = await zaba_scraper._fetch_url(req.url)

    if not html:
        return JSONResponse({"ok": False, "html": None, "error": "all fetch routes blocked"}, status_code=502)

    return JSONResponse({"ok": True, "html": html})
