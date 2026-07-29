#!/usr/bin/env python3
"""
Scrape Runner — Integration Test Script
========================================

Calls the REAL scraper implementations (not mocks) and logs results to the
scrape_results table.

  - FPS:                  service.py directly (local instance or serv01)
  - Anywho / Zabasearch:  the live universal-search Supabase Edge Function
                          (the actual production caller of AnyWhoScraper.ts /
                          ZabasearchScraper.ts — no separate local/prod path,
                          this is a single globally-deployed endpoint)

Usage:
  python scrape_runner.py --target fps --mode local --type summary --input first_name=John last_name=Doe city="San Francisco" state=CA
  python scrape_runner.py --target anywho --mode prod --type summary --input first_name=Jane last_name=Smith
  python scrape_runner.py --target zabasearch --mode prod --type full --input phone="415-555-0123"
  python scrape_runner.py --target quickscan --mode local --type summary --input first_name=John last_name=Doe city="San Francisco" state=CA

Arguments:
  --target      (fps|anywho|zabasearch|quickscan)
  --mode        (local|prod) — only meaningful for fps; anywho/zabasearch always
                hit the single deployed universal-search endpoint regardless
  --type        (summary|full|both) — full only affects anywho/zabasearch response
                completeness in practice (fps always returns full profile data)
  --input       key=value pairs: first_name, last_name, city, state, phone

Environment (.env.local in Vanyshr-mono):
  SUPABASE_URL, SUPABASE_ANON_KEY
  FPS_LOCAL_URL, FPS_PROD_URL, FPS_SERVICE_TOKEN
  CF_RELAY_URL, CF_RELAY_TOKEN  (unused directly here — universal-search owns relay auth)
  QUICKSCAN_MODE
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

from scrape_result_transformer import normalize_fps_row, normalize_relay_rows


def _load_env():
    """Load .env.local from Vanyshr-mono (sibling repo, where secrets are managed)."""
    test_dir = Path(__file__).resolve().parent
    candidates = [
        test_dir.parent.parent / "Vanyshr-mono" / ".env.local",
        test_dir.parent.parent.parent / ".env.local",
        test_dir / ".env.local",
        test_dir.parent / ".env.local",
    ]
    for env_file in candidates:
        if env_file.exists():
            load_dotenv(env_file)
            return
    load_dotenv()


_load_env()

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")

FPS_LOCAL_URL = os.getenv("FPS_LOCAL_URL", "http://localhost:8787")
FPS_PROD_URL = os.getenv("FPS_PROD_URL", "")
FPS_SERVICE_TOKEN = os.getenv("FPS_SERVICE_TOKEN", "")

UNIVERSAL_SEARCH_URL = f"{SUPABASE_URL}/functions/v1/universal-search" if SUPABASE_URL else ""

QUICKSCAN_SEQUENCE = os.getenv("QUICKSCAN_MODE", "fps,anywho,zabasearch").split(",")

SITE_NAME_MAP = {"anywho": "AnyWho", "zabasearch": "Zabasearch"}

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def generate_scrape_id(target: str, timestamp: Optional[datetime] = None) -> str:
    """Generate scrape_id: target.MM.DD.HH.MM"""
    if timestamp is None:
        timestamp = datetime.now()
    return f"{target}.{timestamp.strftime('%m.%d.%H.%M')}"


# ─────────────────────────────────────────────────────────────────────────────
# Scraper Execution
# ─────────────────────────────────────────────────────────────────────────────

class ScraperRunner:
    def __init__(
        self,
        target: str,
        mode: str,
        scrape_type: str,
        input_data: Dict[str, Any],
        verbose: bool = False,
    ):
        self.target = target
        self.mode = mode
        self.scrape_type = scrape_type
        self.input_data = input_data
        self.verbose = verbose
        self.scrape_id = generate_scrape_id(target)

        if self.verbose:
            logger.setLevel(logging.DEBUG)

    async def run_fps(self) -> List[Dict[str, Any]]:
        """Call service.py directly (local instance or serv01)."""
        url = FPS_PROD_URL if self.mode == "prod" else FPS_LOCAL_URL
        endpoint = f"{url.rstrip('/')}/v1/fps/search"

        body = {
            "first_name": self.input_data.get("first_name", ""),
            "last_name": self.input_data.get("last_name", ""),
            "city": self.input_data.get("city") or None,
            "state": self.input_data.get("state") or None,
        }
        headers = {"Content-Type": "application/json"}
        if self.mode == "prod" and FPS_SERVICE_TOKEN:
            headers["Authorization"] = f"Bearer {FPS_SERVICE_TOKEN}"

        logger.info(f"[{self.scrape_id}] POST {endpoint} body={body}")

        try:
            async with httpx.AsyncClient(timeout=150.0) as client:
                response = await client.post(endpoint, json=body, headers=headers)
                response_time_ms = int(response.elapsed.total_seconds() * 1000)
                response.raise_for_status()
                data = response.json()

                logger.info(f"[{self.scrape_id}] FPS status={data.get('status')}")

                row = normalize_fps_row(
                    scrape_id=self.scrape_id,
                    mode=self.mode,
                    scrape_type=self.scrape_type,
                    input_data=self.input_data,
                    fps_response=data,
                    response_time_ms=response_time_ms,
                    response_bytes=len(response.content),
                )
                return [row]

        except httpx.TimeoutException:
            logger.error(f"[{self.scrape_id}] FPS timeout")
            return [normalize_fps_row(
                self.scrape_id, self.mode, self.scrape_type, self.input_data,
                {"status": "failed", "error": "timeout after 150s"}, 150000, 0,
            )]
        except Exception as e:
            logger.error(f"[{self.scrape_id}] FPS failed: {e}")
            return [normalize_fps_row(
                self.scrape_id, self.mode, self.scrape_type, self.input_data,
                {"status": "failed", "error": str(e)}, 0, 0,
            )]

    async def _run_via_universal_search(self, target: str) -> List[Dict[str, Any]]:
        """Call the live universal-search Edge Function for anywho/zabasearch.

        Note: this writes a real (but ephemeral, 30-min TTL) row to the prod
        quick_scans table — that's how the endpoint is designed to work.
        """
        site_name = SITE_NAME_MAP[target]
        body = {
            "firstName": self.input_data.get("first_name", ""),
            "lastName": self.input_data.get("last_name", ""),
            "city": self.input_data.get("city") or None,
            "state": self.input_data.get("state") or None,
            "zipCode": self.input_data.get("zip") or None,
            "siteName": site_name,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
        }

        logger.info(f"[{self.scrape_id}] POST universal-search siteName={site_name} body={body}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(UNIVERSAL_SEARCH_URL, json=body, headers=headers)
                response_time_ms = int(response.elapsed.total_seconds() * 1000)
                response.raise_for_status()
                data = response.json()

                count = data.get("count", 0)
                logger.info(f"[{self.scrape_id}] {site_name}: {count} match(es), "
                            f"scraper_failed={data.get('scraper_failed')}")

                return normalize_relay_rows(
                    scrape_id=self.scrape_id,
                    target=target,
                    mode=self.mode,
                    scrape_type=self.scrape_type,
                    input_data=self.input_data,
                    universal_search_response=data,
                    response_time_ms=response_time_ms,
                    response_bytes=len(response.content),
                )

        except httpx.TimeoutException:
            logger.error(f"[{self.scrape_id}] {site_name} timeout")
            return [{
                "scrape_id": self.scrape_id, "target": target, "mode": self.mode,
                "scrape_type": self.scrape_type, "input_data": self.input_data,
                "summary_results": None, "full_profile_results": None,
                "errors": "timeout after 120s", "status": "timeout",
                "response_time_ms": 120000, "response_bytes": 0,
            }]
        except Exception as e:
            logger.error(f"[{self.scrape_id}] {site_name} failed: {e}")
            return [{
                "scrape_id": self.scrape_id, "target": target, "mode": self.mode,
                "scrape_type": self.scrape_type, "input_data": self.input_data,
                "summary_results": None, "full_profile_results": None,
                "errors": str(e), "status": "failed",
                "response_time_ms": 0, "response_bytes": 0,
            }]

    async def run_anywho(self) -> List[Dict[str, Any]]:
        return await self._run_via_universal_search("anywho")

    async def run_zabasearch(self) -> List[Dict[str, Any]]:
        return await self._run_via_universal_search("zabasearch")

    async def run(self) -> List[Dict[str, Any]]:
        if self.target == "fps":
            return await self.run_fps()
        elif self.target == "anywho":
            return await self.run_anywho()
        elif self.target == "zabasearch":
            return await self.run_zabasearch()
        else:
            raise ValueError(f"Unknown target: {self.target}")


# ─────────────────────────────────────────────────────────────────────────────
# Database Logging
# ─────────────────────────────────────────────────────────────────────────────

async def log_rows_to_db(rows: List[Dict[str, Any]]) -> bool:
    """Insert pre-built DB rows into scrape_results."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL or SUPABASE_ANON_KEY not set")
        return False
    if not rows:
        return True

    url = f"{SUPABASE_URL}/rest/v1/scrape_results"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, row in enumerate(rows):
            try:
                response = await client.post(url, json=row, headers=headers)
                response.raise_for_status()
                logger.debug(f"[{row['scrape_id']}] row {i + 1}/{len(rows)} inserted")
            except Exception as e:
                logger.error(f"[{row['scrape_id']}] insert failed for row {i + 1}: {e}")
                return False

    logger.info(f"[{rows[0]['scrape_id']}] {len(rows)} row(s) logged to DB")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Runner — call real scrapers, log results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--target", required=True, choices=["fps", "anywho", "zabasearch", "quickscan"])
    parser.add_argument("--mode", required=True, choices=["local", "prod"])
    parser.add_argument("--type", required=True, choices=["summary", "full", "both"])
    parser.add_argument("--input", nargs="*", default=[])
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return parser.parse_args()


def parse_input(input_list: List[str]) -> Dict[str, Any]:
    result = {}
    for item in input_list:
        if "=" not in item:
            raise ValueError(f"Invalid input format: {item} (expected key=value)")
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


async def main():
    args = parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        input_data = parse_input(args.input)
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        sys.exit(1)

    logger.info(f"Starting scrape: {args.target} ({args.mode}, {args.type})")

    all_rows: List[Dict[str, Any]] = []

    if args.target == "quickscan":
        for target in QUICKSCAN_SEQUENCE:
            runner = ScraperRunner(target, args.mode, args.type, input_data, args.verbose)
            all_rows.extend(await runner.run())
    else:
        runner = ScraperRunner(args.target, args.mode, args.type, input_data, args.verbose)
        all_rows.extend(await runner.run())

    if not args.no_log:
        await log_rows_to_db(all_rows)

    print(json.dumps(all_rows, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
