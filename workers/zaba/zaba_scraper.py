#!/usr/bin/env python3
"""
Zaba Scraper — FlameProxies-first fetch (curl) + BeautifulSoup parse.

Prod preference: minimize hits on the host residential IP.
  1. FlameProxies pool via curl --proxy (same stack that passed A/B)
  2. Optional last-resort direct curl on this machine (ZABA_DIRECT_FALLBACK=1)

Standalone usage:
    python zaba_scraper.py --first James --last Oehring --city Cameron --state MO

Environment:
    FLAMEPROXIES_API_KEY      — required for primary fetch path
    FLAMEPROXIES_PACKAGE_ID   — default 2549
    ZABA_PROXY_ATTEMPTS       — max Flame IPs to try per URL (default 5)
    ZABA_DIRECT_FALLBACK      — "1" = allow host residential IP only after all
                                proxies fail (minimize personal IP burn)
"""

import argparse
import asyncio
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ── Env loading ────────────────────────────────────────────────────────────────

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

log = logging.getLogger("zaba-scraper")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # identity avoids brotli issues if brotli isn't installed in the venv
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "DNT": "1",
}

BLOCK_PATTERNS = [
    "Just a moment",
    "Checking your browser",
    "Enable JavaScript and cookies to continue",
    "cf-browser-verification",
    "Attention Required! | Cloudflare",
    "Sorry, you have been blocked",
    "Access denied",
    "cf_chl_opt",
    "challenge-platform",
]


def _direct_fallback_enabled() -> bool:
    """Host residential IP only as last resort when proxies exhausted."""
    return os.environ.get("ZABA_DIRECT_FALLBACK", "").strip() == "1"


def _flame_api_key() -> str:
    return os.environ.get("FLAMEPROXIES_API_KEY", "").strip()


def _flame_package_id() -> int:
    return int(os.environ.get("FLAMEPROXIES_PACKAGE_ID", "2549"))


def _max_proxy_attempts() -> int:
    # Default 5 — A/B saw ~40% per-IP success; 5 attempts is usually enough
    return int(os.environ.get("ZABA_PROXY_ATTEMPTS", "5"))


def _curl_bin() -> str:
    return "curl.exe" if os.name == "nt" else "curl"


# ── Proxy ──────────────────────────────────────────────────────────────────────

def _proxy_url_from_parts(raw: str) -> Optional[str]:
    """Convert host:port:user:pass → http://user:pass@host:port"""
    parts = raw.split(":")
    if len(parts) < 4:
        log.warning("Unexpected proxy format: %s", raw[:40])
        return None
    host, port, user, password = parts[0], parts[1], parts[2], ":".join(parts[3:])
    return f"http://{user}:{password}@{host}:{port}"


async def _get_flameproxies_list() -> list[str]:
    """Fetch residential proxy credential(s) from FlameProxies API."""
    api_key = _flame_api_key()
    if not api_key:
        log.warning("FLAMEPROXIES_API_KEY not set")
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
            raw_list = data.get("proxies") or []
            urls = []
            for raw in raw_list:
                u = _proxy_url_from_parts(raw)
                if u:
                    urls.append(u)
            log.info("FlameProxies returned %d proxy credential(s)", len(urls))
            return urls
    except Exception as e:
        log.warning("FlameProxies credential fetch failed: %s", e)
        return []


def _is_blocked(status: int, html: str) -> bool:
    if status in (403, 429, 503):
        return True
    if any(p in html for p in BLOCK_PATTERNS):
        return True
    if len(html) < 5000:
        return True
    return False


async def _curl_fetch(url: str, proxy_url: Optional[str] = None) -> Optional[str]:
    """
    Fetch URL with system curl (curl.exe on Windows).
    A/B on serv01: curl works for Zaba; httpx TLS fingerprint often gets 403.
    Optional --proxy for Flame credentials.
    """
    curl_bin = _curl_bin()
    label = f"proxy {proxy_url.split('@')[-1]}" if proxy_url else "direct (host IP)"
    log.info("curl fetch [%s]: %s", label, url)

    cmd = [
        curl_bin, "-sS", "-L",
        "-A", BROWSER_HEADERS["User-Agent"],
        "-H", f"Accept: {BROWSER_HEADERS['Accept']}",
        "-H", f"Accept-Language: {BROWSER_HEADERS['Accept-Language']}",
        "-H", "Accept-Encoding: identity",
        "-H", "Upgrade-Insecure-Requests: 1",
        "-H", f"Sec-Fetch-Dest: {BROWSER_HEADERS['Sec-Fetch-Dest']}",
        "-H", f"Sec-Fetch-Mode: {BROWSER_HEADERS['Sec-Fetch-Mode']}",
        "-H", f"Sec-Fetch-Site: {BROWSER_HEADERS['Sec-Fetch-Site']}",
        "-H", f"Sec-Fetch-User: {BROWSER_HEADERS['Sec-Fetch-User']}",
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
    Prod order (minimize personal IP):
      1) Flame via curl --proxy (retry up to ZABA_PROXY_ATTEMPTS)
      2) Host residential IP via curl only if ZABA_DIRECT_FALLBACK=1
    """
    proxies = await _get_flameproxies_list()
    max_attempts = _max_proxy_attempts()
    if not proxies:
        log.warning("No FlameProxies credentials — skip proxy path")
    else:
        n = min(len(proxies), max_attempts)
        log.info("Primary path: FlameProxies via curl (%d attempt(s))", n)
        for i, proxy_url in enumerate(proxies[:max_attempts]):
            log.info("Flame attempt %d/%d", i + 1, n)
            html = await _curl_fetch(url, proxy_url=proxy_url)
            if html:
                return html

    if _direct_fallback_enabled():
        log.warning(
            "All Flame attempts failed — LAST RESORT: host residential IP "
            "(ZABA_DIRECT_FALLBACK=1)"
        )
        html = await _curl_fetch(url, proxy_url=None)
        if html:
            return html
    else:
        log.warning(
            "ZABA_DIRECT_FALLBACK is OFF — not using host residential IP. "
            "Set ZABA_DIRECT_FALLBACK=1 to allow last-resort personal IP."
        )

    log.error("All fetch routes failed for: %s", url)
    return None


# ── URL builder ────────────────────────────────────────────────────────────────

_STATE_ABBR_TO_NAME = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico", "NY": "new-york",
    "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode-island", "SC": "south-carolina",
    "SD": "south-dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west-virginia",
    "WI": "wisconsin", "WY": "wyoming", "DC": "district-of-columbia",
}

def _build_url(first: str, last: str, city: Optional[str], state: Optional[str]) -> str:
    name_slug = f"{first.lower().replace(' ', '-')}-{last.lower().replace(' ', '-')}"
    url = f"https://www.zabasearch.com/people/{name_slug}"
    if state:
        state_slug = _STATE_ABBR_TO_NAME.get(state.upper(), state.lower().replace(" ", "-"))
        url += f"/{state_slug}"
        if city:
            city_slug = city.lower().replace(" ", "-")
            url += f"/{city_slug}"
    return url


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse_profiles(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    person_divs = soup.find_all("div", class_="person")
    log.info("Found %d div.person cards", len(person_divs))

    profiles = []
    for div in person_divs:
        try:
            profiles.append(_parse_one(div))
        except Exception as e:
            log.warning("Error parsing person div: %s", e)

    return profiles


def _parse_one(div) -> dict:
    # ID + age from data attrs
    data_id  = div.get("data-id", "")
    data_age = div.get("data-age", "")
    age = data_age if re.match(r"^\d{1,3}$", data_age) else None

    # Name — h2 a has aria-label="View report for {Name}" which is reliable
    name = ""
    h2_a = div.select_one("#container-name h2 a")
    if h2_a:
        aria = h2_a.get("aria-label", "")
        if aria.startswith("View report for "):
            name = aria[len("View report for "):].strip()
        else:
            name = h2_a.get_text(strip=True)
    if not name:
        h2 = div.select_one("#container-name h2")
        if h2:
            name = h2.get_text(strip=True)

    # Aliases
    aliases = []
    alt_names = div.find("div", id="container-alt-names")
    if alt_names:
        for li in alt_names.select("ul li"):
            t = li.get_text(strip=True)
            if t and len(t) > 1:
                aliases.append(t)

    # Relatives
    relatives = []
    for h3 in div.find_all("h3"):
        if h3.get_text(strip=True) == "Possible Relatives":
            ul = h3.find_next_sibling("ul") or (h3.parent and h3.parent.find("ul"))
            if ul:
                for li in ul.find_all("li"):
                    t = li.get_text(strip=True)
                    if t and len(t) > 2:
                        relatives.append({"name": t})
            break

    # Phones — from "Associated Phone Numbers" ul (tracking links, extract from href)
    phones = []
    phone_snippet = ""
    seen_phones = set()
    for h3 in div.find_all("h3"):
        if h3.get_text(strip=True) == "Associated Phone Numbers":
            ul = h3.find_next_sibling("ul") or (h3.parent and h3.parent.find("ul"))
            if ul:
                for i, a in enumerate(ul.find_all("a")):
                    t = a.get_text(strip=True)
                    if t and t not in seen_phones and re.match(r"\(\d{3}\)", t):
                        seen_phones.add(t)
                        phones.append({"number": t, "type": "unknown", "primary": i == 0})
                        if i == 0:
                            phone_snippet = t
            break

    # Also check "Last Known Phone Numbers" section for richer data (type/provider)
    phone_detail = {}
    for h3 in div.find_all("h3"):
        if h3.get_text(strip=True) == "Last Known Phone Numbers":
            parent = h3.parent
            if parent:
                for phone_div in parent.select("div.flex > div"):
                    h4 = phone_div.find("h4")
                    if not h4:
                        continue
                    number_text = h4.get_text(separator=" ", strip=True)
                    # strip "(Primary Phone)" etc
                    number = re.sub(r"\s*\(.*?\)\s*", "", number_text).strip()
                    ps = [p.get_text(strip=True) for p in phone_div.find_all("p")]
                    phone_type = ps[0] if ps else "unknown"
                    provider   = ps[1] if len(ps) > 1 else None
                    first_rep  = ps[2] if len(ps) > 2 else None
                    phone_detail[number] = {
                        "type": phone_type.lower(),
                        "provider": provider,
                        "first_reported": first_rep,
                    }
            break

    # Merge detail into phones list
    for p in phones:
        detail = phone_detail.get(p["number"], {})
        p.update({k: v for k, v in detail.items() if v})

    # Last Known Address
    addresses = []
    city_state = ""
    for h3 in div.find_all("h3"):
        if h3.get_text(strip=True) == "Last Known Address":
            parent = h3.parent
            if parent:
                p_tag = parent.select_one("div.flex div p")
                if p_tag:
                    # Use separator="\n" to split street from city/state/zip across <br>
                    raw = p_tag.get_text(separator="\n", strip=True)
                    lines = [l.strip() for l in raw.splitlines() if l.strip()]
                    street = lines[0] if lines else ""
                    csz    = lines[1] if len(lines) > 1 else ""
                    m = re.match(r"^(.+?),\s*([A-Za-z\s]+?)\s+(\d{5})", csz)
                    if m:
                        city_state = f"{street}, {m.group(1).strip()}, {m.group(2).strip()}"
                        addresses.append({
                            "full_address": f"{street}, {csz}",
                            "street": street,
                            "city": m.group(1).strip(),
                            "state": m.group(2).strip(),
                            "zip": m.group(3),
                            "is_current": True,
                        })
                    elif street:
                        city_state = raw.replace("\n", ", ")
                        addresses.append({"full_address": city_state, "is_current": True})
            break

    # Past Addresses
    for h3 in div.find_all("h3"):
        if h3.get_text(strip=True) == "Past Addresses":
            ul = h3.find_next_sibling("ul") or (h3.parent and h3.parent.find("ul"))
            if ul:
                for li in ul.find_all("li"):
                    raw = li.get_text(separator="\n", strip=True)
                    lines = [l.strip() for l in raw.splitlines() if l.strip()]
                    street = lines[0] if lines else ""
                    csz    = lines[1] if len(lines) > 1 else ""
                    m = re.match(r"^(.+?),\s*([A-Za-z\s]+?)\s+(\d{5})", csz)
                    if m:
                        addresses.append({
                            "full_address": f"{street}, {csz}",
                            "street": street,
                            "city": m.group(1).strip(),
                            "state": m.group(2).strip(),
                            "zip": m.group(3),
                            "is_current": False,
                        })
                    elif street:
                        addresses.append({"full_address": raw.replace("\n", ", "), "is_current": False})
            break

    # Emails
    emails = []
    for h3 in div.find_all("h3"):
        if h3.get_text(strip=True) == "Associated Email Addresses":
            ul = h3.find_next_sibling("ul") or (h3.parent and h3.parent.find("ul"))
            if ul:
                for li in ul.find_all("li"):
                    text = li.get_text(strip=True)
                    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
                    if m:
                        email = m.group(0).lower()
                        if "zabasearch" not in email and "intelius" not in email:
                            emails.append({"email": email})
            break

    # JSON-LD structured data (bonus — Zaba includes it, very reliable)
    json_ld = {}
    script = div.find("script", type="application/ld+json")
    if script:
        import json
        try:
            json_ld = json.loads(script.string or "{}")
        except Exception:
            pass

    # Detail link — NOT the Intelius tracking link; use structured data or skip
    detail_link = None
    if json_ld.get("url"):
        detail_link = json_ld["url"]

    return {
        "id": data_id,
        "name": name or json_ld.get("name", ""),
        "age": age,
        "city_state": city_state,
        "phone_snippet": phone_snippet,
        "phones": phones or None,
        "addresses": addresses or None,
        "relatives": relatives or None,
        "aliases": aliases or None,
        "emails": emails or None,
        "detail_link": detail_link,
        "source": "Zabasearch",
    }


# ── Public API ─────────────────────────────────────────────────────────────────

async def search(
    first_name: str,
    last_name: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> dict:
    """
    Main entry point. Returns:
        { status: "success", profiles: [...], count: N }
        { status: "no_results", profiles: [], count: 0 }
        { status: "failed", error: "..." }
    """
    t0 = time.monotonic()

    # Try city+state, fall back to state-only, then no location
    attempts = []
    if city and state:
        attempts.append((city, state))
    if state:
        attempts.append((None, state))
    attempts.append((None, None))

    html = None
    used_url = None
    for attempt_city, attempt_state in attempts:
        url = _build_url(first_name, last_name, attempt_city, attempt_state)
        log.info("Fetching: %s", url)
        html = await _fetch_url(url)
        if html:
            used_url = url
            break
        if attempt_city:
            log.info("No results with city, retrying state-only")
        elif attempt_state:
            log.info("No results with state, retrying without location")

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if not html:
        return {"status": "failed", "error": "all fetch routes blocked", "elapsed_ms": elapsed_ms}

    profiles = _parse_profiles(html)
    log.info("Parsed %d profiles in %dms", len(profiles), elapsed_ms)

    return {
        "status": "success" if profiles else "no_results",
        "profiles": profiles,
        "count": len(profiles),
        "url": used_url,
        "elapsed_ms": elapsed_ms,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Zaba scraper CLI")
    parser.add_argument("--first", required=True)
    parser.add_argument("--last",  required=True)
    parser.add_argument("--city",  default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--direct", action="store_true", help="Allow direct fetch fallback")
    args = parser.parse_args()

    if args.direct:
        os.environ["ZABA_DIRECT_FALLBACK"] = "1"

    result = asyncio.run(search(args.first, args.last, args.city, args.state))
    print(json.dumps(result, indent=2))
