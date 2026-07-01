#!/usr/bin/env python3
"""Runs IMMEDIATELY after a Camoufox mint (same batch) so the cf_clearance is
seconds old. Full curl_cffi data path: summary -> extract _id_ detail URL ->
detail page. Saves summary.html + detail.html into OUT_DIR for the parser.
cf_clearance is short-lived (~15 min) and IP-locked, hence the tight chaining."""
import json
import os
import re
from curl_cffi import requests

OUT = os.environ.get("OUT_DIR", ".")
CK = json.load(open(os.path.join(OUT, "cf_cookies.json")))
COOKIES = {c["name"]: c["value"] for c in CK["cookies"]}
UA = CK["ua"]
FIRST, LAST, CITY, STATE = "James", "Oehring", "Cameron", "MO"
slug = f"{FIRST}-{LAST}".lower().replace(" ", "-") + "_" + f"{CITY}-{STATE}".lower().replace(" ", "-")
SUMMARY = f"https://www.fastpeoplesearch.com/name/{slug}"


def get(url, ref):
    return requests.get(url, cookies=COOKIES,
                        headers={"User-Agent": UA, "Referer": ref},
                        impersonate="firefox135", timeout=30)


s = get(SUMMARY, "https://www.google.com/")
real = "public record" in s.text.lower()
print(f"[flow] summary {s.status_code} bytes={len(s.text)} real={real}")
open(os.path.join(OUT, "summary.html"), "w", encoding="utf-8").write(s.text)

# First person detail link (the searched person is the top result).
m = re.search(r'href="(/[a-z0-9-]+_id_[A-Za-z0-9-]+)"', s.text, re.I)
if not m:
    print("[flow] NO _id_ detail link in summary")
else:
    durl = "https://www.fastpeoplesearch.com" + m.group(1)
    print(f"[flow] detail url: {durl}")
    d = get(durl, SUMMARY)
    dl = d.text.lower()
    real_d = "age" in dl and ("phone" in dl or "address" in dl)
    print(f"[flow] detail {d.status_code} bytes={len(d.text)} real={real_d}")
    open(os.path.join(OUT, "detail.html"), "w", encoding="utf-8").write(d.text)
