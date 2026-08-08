#!/usr/bin/env python3
"""
NPD Scraper — National Public Data people search.

Phase 0 route decision (2026-08-07): **A — Direct curl on serv01**.
  - Laptop/DC curl+httpx: 0/5 (CF 403/429)
  - serv01 curl direct: 4/5 person results
  - serv01 httpx: 0/5 (TLS fingerprint)
  - Flame+curl: 0/5 (403)
  - Browser not required

Fetch: system curl (not httpx). Direct is primary.
Optional Flame via NPD_USE_FLAME=1 (currently blocked by NPD; kept for parity).

URL patterns:
  /people/{last[0]}/{first}-{last}/
  /people/{last[0]}/{first}-{last}/{state}/
  /people/{last[0]}/{first}-{last}/{state}/{city}/
  /people/{last[0]}/{first}-{last}/{state}/{city}/{id}/   (detail)

Standalone:
    python npd_scraper.py --first James --last Oehring --city Cameron --state MO
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


def _load_env():
    here = Path(__file__).resolve().parent
    candidates = [
        here / ".env",
        here / ".env.txt",
        here.parent.parent.parent / "Vanyshr-mono" / ".env.local",
        here.parent.parent.parent / ".env.local",
    ]
    for c in candidates:
        if c.exists():
            load_dotenv(c)
            return


_load_env()

log = logging.getLogger("npd-scraper")

BASE = "https://nationalpublicdata.com"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

BLOCK_PATTERNS = [
    "Just a moment",
    "Checking your browser",
    "Enable JavaScript and cookies to continue",
    "cf-browser-verification",
    "Attention Required! | Cloudflare",
    "Sorry, you have been blocked",
    "cf_chl_opt",
]


def _flame_api_key() -> str:
    return os.environ.get("FLAMEPROXIES_API_KEY", "").strip()


def _flame_package_id() -> int:
    return int(os.environ.get("FLAMEPROXIES_PACKAGE_ID", "2549"))


def _use_flame() -> bool:
    """Opt-in Flame path. Default off — Phase 0 scored Flame 0/5 for NPD."""
    return os.environ.get("NPD_USE_FLAME", "").strip() == "1"


def _max_proxy_attempts() -> int:
    return int(os.environ.get("NPD_PROXY_ATTEMPTS", "3"))


def _curl_bin() -> str:
    return "curl.exe" if os.name == "nt" else "curl"


def _slug(value: str) -> str:
    s = value.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def build_url(
    first: str,
    last: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> str:
    """Build NPD people-search URL."""
    first_slug = _slug(first)
    last_slug = _slug(last)
    if not first_slug or not last_slug:
        raise ValueError("first and last name required")
    letter = last_slug[0]
    url = f"{BASE}/people/{letter}/{first_slug}-{last_slug}/"
    if state:
        # NPD path uses 2-letter state abbr lowercased (e.g. /mo/)
        st = state.strip().lower()
        if len(st) > 2:
            st = st[:2]
        url += f"{st}/"
        if city:
            url += f"{_slug(city)}/"
    return url


def _is_blocked(status: int, html: str) -> bool:
    if status in (403, 429, 503):
        return True
    if any(p in html for p in BLOCK_PATTERNS):
        # real pages also embed CF email-decode / jsd scripts — require short page or title
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        title = (title_m.group(1) if title_m else "").strip()
        if "Just a moment" in title or "Attention Required" in title:
            return True
        if len(html) < 8000 and ("challenge-platform" in html or "cf-browser-verification" in html):
            return True
        if "Sorry, you have been blocked" in html:
            return True
    return False


def _proxy_url_from_parts(raw: str) -> Optional[str]:
    parts = raw.split(":")
    if len(parts) < 4:
        return None
    host, port, user, password = parts[0], parts[1], parts[2], ":".join(parts[3:])
    return f"http://{user}:{password}@{host}:{port}"


async def _get_flameproxies_list() -> list[str]:
    api_key = _flame_api_key()
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://flameproxies.com/api/customer/proxies/generate",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"package_id": _flame_package_id(), "country": "US"},
            )
            r.raise_for_status()
            data = r.json()
            urls = []
            for raw in data.get("proxies") or []:
                u = _proxy_url_from_parts(raw)
                if u:
                    urls.append(u)
            return urls
    except Exception as e:
        log.warning("FlameProxies credential fetch failed: %s", e)
        return []


async def _curl_fetch(url: str, proxy_url: Optional[str] = None) -> Optional[str]:
    curl_bin = _curl_bin()
    label = f"proxy {proxy_url.split('@')[-1]}" if proxy_url else "direct"
    log.info("curl fetch [%s]: %s", label, url)

    cmd = [
        curl_bin, "-sS", "-L",
        "-A", BROWSER_HEADERS["User-Agent"],
        "-H", f"Accept: {BROWSER_HEADERS['Accept']}",
        "-H", f"Accept-Language: {BROWSER_HEADERS['Accept-Language']}",
        "-H", "Accept-Encoding: identity",
        "-H", "Upgrade-Insecure-Requests: 1",
        "--max-time", "45",
        "-w", "\n__CURL_HTTP_CODE__:%{http_code}",
    ]
    if proxy_url:
        cmd.extend(["--proxy", proxy_url])
    cmd.append(url)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=50.0)
        raw = stdout.decode("utf-8", errors="replace")
        status = 0
        html = raw
        if "__CURL_HTTP_CODE__:" in raw:
            html, _, code_part = raw.rpartition("__CURL_HTTP_CODE__:")
            html = html.rstrip("\n")
            try:
                status = int(code_part.strip())
            except ValueError:
                status = 0
        err = stderr.decode("utf-8", errors="replace")[:200]
        if proc.returncode not in (0, None) and not html:
            log.warning("curl [%s] failed rc=%s stderr=%s", label, proc.returncode, err)
            return None
        if not _is_blocked(status or 200, html):
            log.info("curl [%s] success — status=%s len=%s", label, status, len(html))
            return html
        log.warning("curl [%s] blocked — status=%s len=%s", label, status, len(html))
    except FileNotFoundError:
        log.warning("%s not found on PATH", curl_bin)
    except Exception as e:
        log.warning("curl [%s] error: %s", label, e)
    return None


async def _fetch_url(url: str) -> Optional[str]:
    """
    Route A: direct curl primary.
    If NPD_USE_FLAME=1, try Flame first then direct.
    """
    if _use_flame():
        proxies = await _get_flameproxies_list()
        max_attempts = _max_proxy_attempts()
        if proxies:
            n = min(len(proxies), max_attempts)
            log.info("Opt-in Flame path (%d attempt(s))", n)
            for i, proxy_url in enumerate(proxies[:max_attempts]):
                log.info("Flame attempt %d/%d", i + 1, n)
                html = await _curl_fetch(url, proxy_url=proxy_url)
                if html:
                    return html
        else:
            log.warning("NPD_USE_FLAME=1 but no Flame credentials")

    # Primary (Route A): host residential / serv01 direct curl
    for attempt in range(1, 4):
        html = await _curl_fetch(url, proxy_url=None)
        if html:
            return html
        # brief backoff for 429 rate windows
        await asyncio.sleep(1.5 * attempt)

    log.error("All fetch routes failed for: %s", url)
    return None


def _format_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


def _age_from_birth_year(birth: Optional[str]) -> Optional[str]:
    if not birth:
        return None
    m = re.search(r"(19|20)\d{2}", str(birth))
    if not m:
        return None
    year = int(m.group(0))
    age = datetime.now(timezone.utc).year - year
    if 0 < age < 120:
        return str(age)
    return None


def _addr_from_place(place: dict) -> Optional[dict]:
    addr = place.get("address") or {}
    if not isinstance(addr, dict):
        return None
    street = addr.get("streetAddress") or ""
    city = addr.get("addressLocality") or ""
    state = addr.get("addressRegion") or ""
    zipc = addr.get("postalCode") or ""
    parts = [p for p in [street, city, state, zipc] if p]
    if not parts:
        return None
    full = ", ".join([street, city, state, zipc] if street else [city, state, zipc])
    full = re.sub(r",\s*,", ",", full).strip(", ")
    desc = (place.get("description") or "").lower()
    is_current = "current" in desc
    return {
        "full_address": full,
        "street": street or None,
        "city": city or None,
        "state": state or None,
        "zip": zipc or None,
        "is_current": is_current,
    }


def _profile_from_jsonld(person: dict) -> dict:
    url = person.get("url") or person.get("@id") or ""
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    pid = parts[-1] if parts and parts[-1].startswith("pd") else None

    phones_raw = person.get("telephone") or []
    if isinstance(phones_raw, str):
        phones_raw = [phones_raw]
    phones = []
    for i, p in enumerate(phones_raw):
        num = _format_phone(str(p))
        phones.append({"number": num, "type": "unknown", "primary": i == 0})

    emails_raw = person.get("email") or []
    if isinstance(emails_raw, str):
        emails_raw = [emails_raw]
    emails = [{"email": e.lower()} for e in emails_raw if e and "@" in str(e)]

    relatives = []
    for rel in person.get("relatedTo") or []:
        if isinstance(rel, dict) and rel.get("name"):
            relatives.append({"name": rel["name"]})
        elif isinstance(rel, str):
            relatives.append({"name": rel})

    addresses = []
    city_state = ""
    for place in person.get("HomeLocation") or []:
        if not isinstance(place, dict):
            continue
        a = _addr_from_place(place)
        if a:
            addresses.append(a)
            if a.get("is_current") and a.get("city") and a.get("state"):
                city_state = f"{a['city']}, {a['state']}"

    if not city_state and addresses:
        a0 = addresses[0]
        if a0.get("city") and a0.get("state"):
            city_state = f"{a0['city']}, {a0['state']}"

    birth = person.get("birthDate")
    age = _age_from_birth_year(birth)
    phone_snippet = phones[0]["number"] if phones else ""

    return {
        "id": pid,
        "name": person.get("name") or "",
        "age": age,
        "birth_year": str(birth) if birth else None,
        "city_state": city_state,
        "phone_snippet": phone_snippet,
        "phones": phones or None,
        "addresses": addresses or None,
        "relatives": relatives or None,
        "aliases": None,
        "emails": emails or None,
        "detail_link": url or None,
        "source": "NPD",
    }


def parse_profiles(html: str) -> list[dict]:
    """Extract Person profiles from JSON-LD blocks (preferred) + light HTML fallback."""
    profiles: list[dict] = []
    seen = set()

    for m in re.finditer(
        r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
        html,
        re.S | re.I,
    ):
        raw = m.group(1)
        if '"Person"' not in raw and "'Person'" not in raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if data.get("@type") != "Person":
            continue
        profile = _profile_from_jsonld(data)
        key = profile.get("detail_link") or profile.get("name")
        if key and key not in seen:
            seen.add(key)
            profiles.append(profile)

    if profiles:
        log.info("Parsed %d Person JSON-LD profile(s)", len(profiles))
        return profiles

    # Fallback: name-card headings (sparse)
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 not installed — skipping HTML fallback parse")
        return profiles

    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select(".name-cards-grid-item"):
        h = item.find(["h2", "h3"])
        if not h:
            continue
        name_age = h.get_text(" ", strip=True)
        if not name_age or len(name_age) < 3:
            continue
        age = None
        name = name_age
        am = re.search(r",\s*(\d{1,3})\s*$", name_age)
        if am:
            age = am.group(1)
            name = name_age[: am.start()].strip()
        loc_el = item.select_one(".person-location")
        city_state = loc_el.get_text(" ", strip=True) if loc_el else ""
        link = item.find("a", href=re.compile(r"/people/"))
        detail = link.get("href") if link else None
        if detail and detail.startswith("/"):
            detail = BASE + detail
        key = detail or name
        if key in seen:
            continue
        seen.add(key)
        profiles.append({
            "id": None,
            "name": name,
            "age": age,
            "birth_year": None,
            "city_state": city_state,
            "phone_snippet": "",
            "phones": None,
            "addresses": None,
            "relatives": None,
            "aliases": None,
            "emails": None,
            "detail_link": detail,
            "source": "NPD",
        })

    log.info("Parsed %d profile(s) via HTML fallback", len(profiles))
    return profiles


# Public aliases for tests
is_blocked = _is_blocked
slug = _slug


async def search(
    first_name: str,
    last_name: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> dict[str, Any]:
    """
    Main entry. Returns:
      { status: success|no_results|failed, profiles, count, url?, elapsed_ms, error? }
    """
    t0 = time.monotonic()

    attempts: list[tuple[Optional[str], Optional[str]]] = []
    if city and state:
        attempts.append((city, state))
    if state:
        attempts.append((None, state))
    attempts.append((None, None))

    html = None
    used_url = None
    for attempt_city, attempt_state in attempts:
        url = build_url(first_name, last_name, attempt_city, attempt_state)
        log.info("Fetching: %s", url)
        html = await _fetch_url(url)
        if html:
            used_url = url
            break
        if attempt_city:
            log.info("No HTML with city — retrying state-only")
        elif attempt_state:
            log.info("No HTML with state — retrying name-only")

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if not html:
        return {
            "status": "failed",
            "error": "all fetch routes blocked",
            "profiles": [],
            "count": 0,
            "elapsed_ms": elapsed_ms,
        }

    profiles = parse_profiles(html)
    return {
        "status": "success" if profiles else "no_results",
        "profiles": profiles,
        "count": len(profiles),
        "url": used_url,
        "elapsed_ms": elapsed_ms,
    }


class NPDScraper:
    """Sync-friendly wrapper matching other Vanyshr scrapers."""

    def __init__(self, timeout: int = 40):
        self.timeout = timeout
        self.base_url = BASE

    def search(
        self,
        first: str,
        last: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
    ) -> list[dict]:
        result = asyncio.run(search(first, last, city, state))
        if result.get("status") == "failed":
            raise RuntimeError(result.get("error") or "npd search failed")
        return result.get("profiles") or []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="NPD scraper CLI")
    parser.add_argument("--first", required=True)
    parser.add_argument("--last", required=True)
    parser.add_argument("--city", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--flame", action="store_true", help="Enable NPD_USE_FLAME=1")
    args = parser.parse_args()
    if args.flame:
        os.environ["NPD_USE_FLAME"] = "1"
    result = asyncio.run(search(args.first, args.last, args.city, args.state))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") != "failed" else 1)
