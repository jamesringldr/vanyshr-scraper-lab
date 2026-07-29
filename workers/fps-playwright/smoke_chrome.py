#!/usr/bin/env python3
"""
FPS smoke test — CHROME/EDGE edition (patchright stealth), Google-referer path.

Hypothesis (user, 2026-06-30): Camoufox's anti-detect spoofing is itself the tell.
A real Chromium fingerprint (Edge) auto-approved FPS's Turnstile when visited
manually on serv-01, where Camoufox always needed the checkbox. And the user's
earlier *working* build used the Google-search referer path with chrome-for-testing
and auto-passed BOTH Cloudflare and DataDome. This replicates that.

Stealth = patchright best practices: drive the REAL system browser via channel
(msedge), launch_persistent_context (not launch+new_context), headless=False, and
NO add_init_script / no JS patching (those are detection vectors — the opposite of
the Camoufox build).

Usage:  python smoke_chrome.py <firstName> <lastName> [city] [state]
Env:    CHANNEL (default msedge; e.g. chrome, chrome-beta), SKIP_GOOGLE=1,
        PROFILE_DIR (default ./edge-profile)
Outputs (OUT_DIR, default ./out): run artifacts (screenshot, html, log).
"""
import os
import sys
import time
import random
from datetime import datetime, timezone
from pathlib import Path

from patchright.sync_api import sync_playwright

if len(sys.argv) < 3:
    print("Usage: python smoke_chrome.py <firstName> <lastName> [city] [state]")
    sys.exit(1)
FIRST, LAST = sys.argv[1], sys.argv[2]
CITY = sys.argv[3] if len(sys.argv) > 3 else ""
STATE = sys.argv[4] if len(sys.argv) > 4 else ""

OUT_DIR = Path(os.environ.get("OUT_DIR", str(Path(__file__).parent / "out")))
OUT_DIR.mkdir(parents=True, exist_ok=True)
CHANNEL = os.environ.get("CHANNEL", "msedge")
SKIP_GOOGLE = os.environ.get("SKIP_GOOGLE") == "1"
PROFILE_DIR = os.environ.get("PROFILE_DIR", str(Path(__file__).parent / "edge-profile"))

LOG = []


def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    LOG.append(line)


def flush_log():
    (OUT_DIR / "chrome-smoke.log").write_text("\n".join(LOG), encoding="utf-8")


def jitter(lo, hi):
    time.sleep((lo + random.random() * (hi - lo)) / 1000.0)


def human_type(page, text):
    for ch in text:
        page.keyboard.type(ch)
        jitter(60, 160)


def safe_content(page):
    for _ in range(4):
        try:
            return page.content()
        except Exception:
            jitter(600, 900)
    return ""


def classify(html):
    lc = html.lower()
    # DataDome BLOCK only — NOT the invisible tags.js (js/api-js.datadome.co) that
    # loads on every FPS page. Real block = the captcha or the "enable JS" page.
    if ("enable js and disable any ad blocker" in lc
            or "geo.captcha-delivery.com/captcha" in lc
            or "captcha-delivery.com/captcha" in lc
            or "datadome-captcha" in lc or "dd-captcha" in lc):
        return "datadome"
    # Cloudflare interstitial / Turnstile challenge page.
    if "just a moment" in lc:
        return "turnstile"
    if "challenges.cloudflare.com" in lc and "verify you are human" in lc:
        return "turnstile"
    # FPS results / profile content (the win).
    if ("free public record found" in lc or "free public records found" in lc
            or "past addresses" in lc or "view free details" in lc):
        return "results"
    # FPS homepage (search form present, no results).
    if "search-name-name" in lc or "searchfaker-input" in lc or "find people fast" in lc:
        return "fps_home"
    return "unknown"


def challenge_state(page):
    """Quick read of what's gating us right now (cheap, non-blocking)."""
    try:
        url = page.url
    except Exception:
        url = ""
    c = classify(safe_content(page))
    return url, c


def run():
    label = " ".join(x for x in [FIRST, LAST, CITY, STATE] if x)
    log(f'FPS smoke (patchright/{CHANNEL}) — "{label}"')
    log(f"  profile: {PROFILE_DIR}  skip_google={SKIP_GOOGLE}")

    final = "error"
    with sync_playwright() as p:
        # Persistent context + real browser channel + headed = patchright stealth.
        # channel: real browser (msedge/chrome) OR bundled chrome-for-testing when
        # CHANNEL is "chromium"/"cft"/empty (channel=None → patchright's CfT build).
        _channel = None if CHANNEL.lower() in ("", "chromium", "cft", "none") else CHANNEL
        log(f"  launching: channel={_channel or 'bundled-chrome-for-testing'}")
        ctx = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            channel=_channel,
            headless=False,
            no_viewport=True,
            # chromium_sandbox=True REMOVES the default --no-sandbox flag (and its
            # "unsupported command-line flag" infobar) — a known automation tell that
            # Cloudflare/DataDome fingerprint. A real user's browser is sandboxed.
            chromium_sandbox=True,
            args=["--start-maximized", "--no-first-run", "--no-default-browser-check"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_resp(r):
            u = r.url
            if any(k in u for k in ("challenges.cloudflare", "captcha-delivery",
                                    "datadome", "/cdn-cgi/challenge", "/name/", "/sorry/")):
                log(f"  [http] {r.status} {u[:110]}")
        page.on("response", on_resp)

        try:
            fps_url = "https://www.fastpeoplesearch.com/"
            direct_name = os.environ.get("DIRECT_NAME") == "1"
            if direct_name:
                slug = (f"{FIRST}-{LAST}".strip().lower().replace(" ", "-")
                        + "_" + f"{CITY}-{STATE}".strip().lower().replace(" ", "-"))
                direct_url = f"https://www.fastpeoplesearch.com/name/{slug}"
                log(f"[1] DIRECT_NAME — straight to results URL (no form): {direct_url}")
                page.goto(direct_url, referer="https://www.google.com/",
                          wait_until="domcontentloaded", timeout=30000)
            elif SKIP_GOOGLE:
                log("[1] SKIP_GOOGLE — direct to FPS with Google referer")
                page.goto(fps_url, referer="https://www.google.com/search?q=fast+people+search",
                          wait_until="domcontentloaded", timeout=30000)
            else:
                log("[1] Google...")
                page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=30000)
                jitter(700, 1400)
                for sel in ['button:has-text("Accept all")', 'button:has-text("I agree")']:
                    b = page.locator(sel).first
                    if b.count() > 0:
                        b.click(); jitter(400, 800); break
                log("[2] Typing search...")
                sb = page.locator('textarea[name="q"], input[name="q"]').first
                sb.wait_for(timeout=10000); sb.click(); jitter(200, 500)
                human_type(page, "fast people search")
                jitter(300, 700); page.keyboard.press("Enter")
                try:
                    page.wait_for_selector("#search, #rso, .g", timeout=15000, state="attached")
                    jitter(1200, 2000)
                    link = page.locator('a[href*="fastpeoplesearch.com"]:visible').first
                    if link.count() > 0:
                        log("[3] Clicking FPS result in Google SERP...")
                        link.click(timeout=12000)
                        page.wait_for_load_state("domcontentloaded", timeout=20000)
                    else:
                        log("[3] No FPS link in SERP — direct with referer")
                        page.goto(fps_url, referer="https://www.google.com/search?q=fast+people+search",
                                  wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    log(f"  Google blocked ({e!s:.60}) — direct with referer")
                    page.goto(fps_url, referer="https://www.google.com/search?q=fast+people+search",
                              wait_until="domcontentloaded", timeout=30000)

            jitter(2500, 4000)
            url, cls = challenge_state(page)
            log(f"[4] landed: {url[:90]}")
            log(f"    title: {page.title()!r}  classification: {cls}")
            page.screenshot(path=str(OUT_DIR / "chrome-landing.png"))

            # If a challenge is showing, just WAIT (real Chrome often auto-passes
            # invisibly). We do NOT click anything — testing the auto-approve claim.
            if cls in ("turnstile", "datadome"):
                log(f"    challenge present ({cls}) — waiting up to 30s for auto-pass (no click)...")
                for _ in range(15):
                    jitter(1800, 2200)
                    url, cls = challenge_state(page)
                    if cls not in ("turnstile", "datadome"):
                        log(f"    auto-passed → {cls} at {url[:70]}")
                        break
                log(f"    after wait: classification={cls}")

            # Search form (real selectors; Enter selects + auto-searches). Skipped in
            # DIRECT_NAME mode — we're already on the /name/ results page.
            name_in = page.locator('#search-name-name, input[name="name"]').first
            if not direct_name and name_in.count() > 0:
                log("[5] FPS search form...")
                name_in.click(); jitter(200, 500); human_type(page, f"{FIRST} {LAST}")
                jitter(300, 700)
                if CITY or STATE:
                    loc = page.locator('#search-name-address, input[name="address"]').first
                    if loc.count() > 0:
                        loc.click(); jitter(150, 400)
                        human_type(page, ", ".join(x for x in [CITY, STATE] if x))
                        jitter(1200, 1800); loc.press("Enter")
                try:
                    page.wait_for_url(lambda u: "/name/" in u or u.rstrip("/") != "https://www.fastpeoplesearch.com",
                                      timeout=30000)
                except Exception:
                    pass
                jitter(3000, 5000)
            else:
                log("[5] no search form on landing")

            url, cls = challenge_state(page)
            # Results-page challenge: wait for auto-pass (no click).
            if cls in ("turnstile", "datadome"):
                log(f"[6] results challenge ({cls}) — waiting up to 40s for auto-pass (no click)...")
                for _ in range(20):
                    jitter(1800, 2200)
                    url, cls = challenge_state(page)
                    if cls in ("results", "success_profile") or "_id_" in url:
                        break
            log(f"[6] final url: {page.url[:100]}")
            html = safe_content(page)
            final = classify(html)
            log(f"    FINAL classification: {final}")
            page.screenshot(path=str(OUT_DIR / "chrome-screenshot.png"))
            (OUT_DIR / "chrome-results.html").write_text(html, encoding="utf-8")
        except Exception as e:
            log(f"ERROR: {e!s:.200}")
            try:
                page.screenshot(path=str(OUT_DIR / "chrome-screenshot.png"))
                (OUT_DIR / "chrome-error.html").write_text(safe_content(page), encoding="utf-8")
            except Exception:
                pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    return final


if __name__ == "__main__":
    try:
        result = run()
    finally:
        flush_log()
    log(f"DONE: {result}")
    flush_log()
