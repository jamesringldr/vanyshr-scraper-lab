#!/usr/bin/env python3
"""Two decisive checks for the curl_cffi hybrid:
  (1) TLS/PQ: does our firefox135 ClientHello carry X25519MLKEM768 + a real FF JA4?
  (2) Cross-person reuse: same cookies on the ORIGINAL url (control) vs a NEW person
      — disambiguates domain-wide reuse from cookie-staleness.
"""
import json
from curl_cffi import requests

CK = json.load(open(r"C:\Users\scraper\fps-scraper\out\cf_cookies.json"))
UA = CK["ua"]
COOKIES = {c["name"]: c["value"] for c in CK["cookies"]}
IMP = "firefox135"

print("=" * 60)
print("(1) TLS / POST-QUANTUM FINGERPRINT CHECK")
try:
    r = requests.get("https://tls.peet.ws/api/all", impersonate=IMP, timeout=30)
    d = r.json()
    tls = d.get("tls", {})
    ja4 = tls.get("ja4") or tls.get("ja4_r")
    # key share / supported groups — look for ML-KEM / Kyber (post-quantum)
    blob = json.dumps(tls).lower()
    pq = any(k in blob for k in ("mlkem", "kyber", "25519mlkem768", "11ec", "x25519kyber"))
    print(f"  user_agent seen: {d.get('http_version','?')} / {(d.get('user_agent') or '')[:50]}")
    print(f"  JA4: {ja4}")
    print(f"  POST-QUANTUM key share present: {pq}")
    # print the key_share groups if available
    for ext in tls.get("extensions", []):
        if "key_share" in str(ext.get("name", "")).lower() or ext.get("name") == "key_share (51)":
            print(f"  key_share: {json.dumps(ext)[:200]}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

print("=" * 60)
print("(2) CROSS-PERSON REUSE (same cookies)")
HEADERS = {"User-Agent": UA, "Referer": "https://www.google.com/"}
tests = [
    ("CONTROL james-oehring", "https://www.fastpeoplesearch.com/name/james-oehring_cameron-mo"),
    ("NEW john-smith",        "https://www.fastpeoplesearch.com/name/john-smith"),
    ("NEW michael-johnson",   "https://www.fastpeoplesearch.com/name/michael-johnson"),
]
for label, url in tests:
    try:
        r = requests.get(url, cookies=COOKIES, headers=HEADERS, impersonate=IMP, timeout=30)
        lc = r.text.lower()
        cf = "security challenge" in lc or "cf-mitigated" in lc
        dd = "captcha-delivery.com/captcha" in lc or "enable js and disable" in lc
        real = ("public record" in lc or "search-name-name" in lc
                or "find people fast" in lc or "view free details" in lc)
        print(f"  {label}: status={r.status_code} bytes={len(r.text)} "
              f"CF={cf} DD={dd} realFPS={real}")
    except Exception as e:
        print(f"  {label}: ERROR {type(e).__name__}: {e}")
