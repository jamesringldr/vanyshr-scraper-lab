#!/usr/bin/env python3
"""Replay harvested Cloudflare cf_clearance via curl_cffi (Firefox-impersonated JA3
TLS, still no JS). Decides whether the clearance is cookie+TLS portable → a fast
HTTP-scraping hybrid, or bound to deeper browser/JS signals → browser-per-request."""
import json
from curl_cffi import requests

CK = json.load(open(r"C:\Users\scraper\fps-scraper\out\cf_cookies.json"))
UA = CK["ua"]
COOKIES = {c["name"]: c["value"] for c in CK["cookies"]}
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/",
    "Upgrade-Insecure-Requests": "1",
}
URLS = [("home", "https://www.fastpeoplesearch.com/"),
        ("name", "https://www.fastpeoplesearch.com/name/james-oehring_cameron-mo")]

# Try Firefox JA3 targets newest-first; use the first curl_cffi accepts.
TARGETS = ["firefox135", "firefox133", "firefox", "firefox132", "firefox120"]
target = None
for t in TARGETS:
    try:
        requests.get("https://example.com", impersonate=t, timeout=15)
        target = t
        break
    except Exception as e:
        if "impersonate" in str(e).lower() or "not" in str(e).lower():
            continue
        target = t  # network err but target accepted
        break
print(f"impersonate target: {target}  (UA={UA[:40]}...)  cookies={list(COOKIES)}")

for label, url in URLS:
    try:
        r = requests.get(url, cookies=COOKIES, headers=HEADERS, impersonate=target, timeout=30)
        b = r.text
        lc = b.lower()
        cf = ("security challenge" in lc or "cf-mitigated" in lc
              or "/cdn-cgi/challenge-platform" in lc or "just a moment" in lc)
        dd = "captcha-delivery.com/captcha" in lc or "enable js and disable" in lc
        real = ("free public record" in lc or "search-name-name" in lc
                or "find people fast" in lc or "view free details" in lc)
        print(f"{label}: status={r.status_code} bytes={len(b)} "
              f"CFchallenge={cf} DDblock={dd} realFPS={real}")
        open(rf"C:\Users\scraper\fps-scraper\out\cffi_{label}.html", "w",
             encoding="utf-8").write(b)
    except Exception as e:
        print(f"{label}: ERROR {type(e).__name__}: {e}")
