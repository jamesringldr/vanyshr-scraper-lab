#!/usr/bin/env python3
"""Parse a FastPeopleSearch detail page (the _id_ profile) into structured JSON —
the exposed-data payload that drives Vanyshr's conversion reveal.

Usage: python parse_detail.py detail.html  ->  prints JSON
"""
import json
import re
import sys

from bs4 import BeautifulSoup


def decode_cfemail(h):
    """Cloudflare email obfuscation: data-cfemail hex, first byte = XOR key."""
    try:
        r = int(h[:2], 16)
        return "".join(chr(int(h[i:i + 2], 16) ^ r) for i in range(2, len(h), 2))
    except Exception:
        return None


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else None


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}

    # ── Name + age (page header) ──────────────────────────────────────────────
    h1 = soup.find("h1")
    name = txt(h1)
    if name:  # h1 = "James Oehring in Cameron, MO (Missouri)" -> "James Oehring"
        name = re.sub(r"\s+in\s+.*$", "", name).strip()
    out["name"] = name
    age_m = re.search(r"\bAge\s+(\d{1,3})\b", soup.get_text(" "))
    out["age"] = int(age_m.group(1)) if age_m else None

    # ── Current address ───────────────────────────────────────────────────────
    cur = soup.find(id="current_address_section")
    if cur:
        a = cur.select_one(".detail-box-content h3 a")
        addr = {}
        if a:
            addr["full"] = txt(a)
            addr["url"] = a.get("href")
        since = cur.find("h2")
        m = re.search(r"\(Since ([^)]+)\)", txt(since) or "")
        if m:
            addr["since"] = m.group(1)
        prop = cur.select_one(".detail-box-content div[style*='font-weight:bold']")
        if prop:
            addr["property"] = txt(prop)
        val = cur.select_one("#current_address_details dd")
        if val:
            addr["estimated_value"] = txt(val)
        # county = first text node after the h3 link
        c = cur.select_one(".detail-box-content")
        if c:
            mc = re.search(r"([A-Z][a-z]+ County)", txt(c) or "")
            if mc:
                addr["county"] = mc.group(1)
        out["current_address"] = addr

    # ── Previous addresses ────────────────────────────────────────────────────
    prev = soup.find(id="previous-addresses")
    out["previous_addresses"] = (
        [txt(a) for a in prev.select("a")] if prev else []
    )

    # ── Phone numbers ─────────────────────────────────────────────────────────
    phones = []
    ph = soup.find(id="phone_number_section")
    if ph:
        for dl in ph.select(".detail-box-phone dl"):
            dds = [txt(d) for d in dl.find_all("dd")]
            phones.append({
                "number": txt(dl.find("dt")),
                "type": dds[0] if len(dds) > 0 else None,
                "carrier": dds[1] if len(dds) > 1 else None,
                "first_reported": re.sub(r"^First reported ", "", dds[2]) if len(dds) > 2 else None,
            })
    out["phones"] = phones

    # ── Emails (Cloudflare-obfuscated) ────────────────────────────────────────
    emails = []
    for a in soup.select("a.__cf_email__[data-cfemail]"):
        e = decode_cfemail(a["data-cfemail"])
        if e:
            emails.append(e)
    out["emails"] = sorted(set(emails))

    # ── Relatives ─────────────────────────────────────────────────────────────
    rels = []
    rl = soup.find(id="relative-links")
    if rl:
        for dl in rl.select("dl"):
            a = dl.find("a")
            dd = txt(dl.find("dd"))
            am = re.search(r"Age (\d+)", dd or "")
            rels.append({
                "name": txt(a),
                "age": int(am.group(1)) if am else None,
                "url": a.get("href") if a else None,
            })
    out["relatives"] = rels

    return out


if __name__ == "__main__":
    html = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    print(json.dumps(parse(html), indent=2, ensure_ascii=False))
