#!/usr/bin/env python3
"""
FPS smoke test — Camoufox edition (Google referral chain)

Why Camoufox: the prior headless-Chromium build reached FPS's Cloudflare
managed Turnstile but never passed it (low client-trust fingerprint). Camoufox
ships a real Firefox fingerprint and injects hardware-aligned WebGL/canvas noise
(defeats Cloudflare's Picasso check) plus a humanized cursor — the two layers
the old code left unaddressed.

Flow: google.com -> search "fast people search" -> [handle reCAPTCHA checkbox if
the "unusual traffic" page appears] -> click FPS result -> [click Turnstile
checkbox] -> fill FPS form -> classify result.

Order of attack is deliberate: Camoufox's better fingerprint may make BOTH the
Google checkbox and the FPS Turnstile pass on a single click. We only build an
audio/STT solver if a run proves the checkbox escalates to an image puzzle.

Usage:  python smoke.py <firstName> <lastName> [city] [state]
Outputs (under OUT_DIR, default /tmp/fps-out):
  fps-smoke.log, fps-screenshot.png, fps-results.html, video/*.webm,
  plus stage snapshots (google-*.png/html, recaptcha-*.png) for review.
"""

import os
import sys
import json
import time
import random
import subprocess
import signal
from datetime import datetime, timezone
from pathlib import Path

from camoufox.sync_api import Camoufox

# Force UTF-8 stdout/stderr so log()'s unicode (━ ✅ → —) can't crash print() on
# Windows' cp1252-redirected console (the `charmap` codec error that made a
# successful run report as "error").
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ─── Args / paths ─────────────────────────────────────────────────────────────

if len(sys.argv) < 3:
    print("Usage: python smoke.py <firstName> <lastName> [city] [state]")
    sys.exit(1)

FIRST, LAST = sys.argv[1], sys.argv[2]
CITY = sys.argv[3] if len(sys.argv) > 3 else ""
STATE = sys.argv[4] if len(sys.argv) > 4 else ""

OUT_DIR = Path(os.environ.get("OUT_DIR", "/tmp/fps-out"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Local headed mode (macOS/dev): skip the Linux-only Xvfb + ffmpeg recording and run
# Camoufox on the real display so you can watch live. Everything else is identical —
# same os=["windows"] spoof, prefs, and flow. Set LOCAL_HEADED=1. Isolation Rung 1.
LOCAL = os.environ.get("LOCAL_HEADED") == "1"

# Native-fingerprint toggle: when set, drop the os=["windows"] spoof and let
# Camoufox use the host OS. Tests the Windows-UA-on-Apple-GPU mismatch theory.
NATIVE_FP = os.environ.get("NATIVE_FP") == "1"


def _load_dotenv():
    """Minimal .env loader (script dir). Populates os.environ without overriding
    values already set. Handles CRLF/LF cleanly — avoids cmd batch quoting of the
    FlameProxies secret on the Windows box."""
    envf = Path(__file__).parent / ".env"
    if not envf.exists():
        return
    for line in envf.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

# ─── Xvfb + ffmpeg video recording ───────────────────────────────────────────
# Playwright's built-in record_video_dir doesn't finalize correctly with
# Firefox in virtual-display mode. We manage Xvfb ourselves and record via
# ffmpeg capturing the X11 display — gives a real, playable MP4.

DISPLAY_NUM = 99
DISPLAY = f":{DISPLAY_NUM}"
VIDEO_PATH = str(OUT_DIR / "fps-session.mp4")

_xvfb_proc = None
_ffmpeg_proc = None


def start_display_and_recording():
    global _xvfb_proc, _ffmpeg_proc
    if LOCAL:
        log("  local headed mode — native display, no Xvfb/ffmpeg (watch live)")
        return
    # Start Xvfb
    _xvfb_proc = subprocess.Popen(
        ["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = DISPLAY
    time.sleep(1.0)  # give Xvfb time to start
    # Start ffmpeg recording
    _ffmpeg_proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-video_size", "1280x800", "-framerate", "15",
         "-f", "x11grab", "-i", DISPLAY,
         "-vcodec", "libx264", "-preset", "ultrafast", "-crf", "28",
         VIDEO_PATH],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def stop_recording():
    global _ffmpeg_proc, _xvfb_proc
    if LOCAL:
        return
    if _ffmpeg_proc:
        try:
            _ffmpeg_proc.send_signal(signal.SIGINT)  # graceful stop → finalizes MP4
            _ffmpeg_proc.wait(timeout=10)
        except Exception:
            _ffmpeg_proc.kill()
        _ffmpeg_proc = None
    if _xvfb_proc:
        try:
            _xvfb_proc.terminate()
            _xvfb_proc.wait(timeout=5)
        except Exception:
            _xvfb_proc.kill()
        _xvfb_proc = None

# Residential proxy. Two ways to supply one:
#  (a) explicit env: PROXY_SERVER=http://host:port  PROXY_USER=...  PROXY_PASS=...
#  (b) USE_FLAME=1 + FLAMEPROXIES_API_KEY → auto-fetch a fresh rotating residential
#      IP from the FlameProxies pool (the always-on box does this itself each run).
PROXY = None


def _fetch_flameproxies():
    """Fetch one fresh FlameProxies residential IP. Returns proxy dict or None."""
    import urllib.request
    api_key = os.environ.get("FLAMEPROXIES_API_KEY", "")
    if not api_key:
        return None
    pkg = int(os.environ.get("FLAMEPROXIES_PACKAGE_ID", "2549"))
    country = os.environ.get("FLAMEPROXIES_COUNTRY", "US")
    body = json.dumps({"package_id": pkg, "country": country}).encode()
    req = urllib.request.Request(
        "https://flameproxies.com/api/customer/proxies/generate",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.4.0",  # FlameProxies WAF 403s the urllib UA
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        host, port, user, pw = data["proxies"][0].split(":")
        return {"server": f"http://{host}:{port}", "username": user, "password": pw}
    except Exception as e:
        print(f"  FlameProxies fetch failed: {e}")
        return None


if os.environ.get("PROXY_SERVER"):
    PROXY = {"server": os.environ["PROXY_SERVER"]}
    if os.environ.get("PROXY_USER"):
        PROXY["username"] = os.environ["PROXY_USER"]
        PROXY["password"] = os.environ.get("PROXY_PASS", "")
elif os.environ.get("USE_FLAME") == "1":
    PROXY = _fetch_flameproxies()

# ─── Logging ──────────────────────────────────────────────────────────────────

LOG = []


def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    LOG.append(line)


def flush_log():
    (OUT_DIR / "fps-smoke.log").write_text("\n".join(LOG), encoding="utf-8")


def sleep(ms):
    time.sleep(ms / 1000.0)


def jitter(lo, hi):
    sleep(lo + random.random() * (hi - lo))


# ─── Human typing (Camoufox humanizes the cursor; typing is on us) ────────────

NEARBY = {
    "a": "sq", "b": "vgn", "c": "xdv", "d": "sec", "e": "wr", "f": "dgr",
    "g": "fht", "h": "gj", "i": "ou", "j": "hk", "k": "jl", "l": "k",
    "m": "n", "n": "mb", "o": "ip", "p": "o", "q": "wa", "r": "et",
    "s": "ad", "t": "ry", "u": "yi", "v": "cb", "w": "qe", "x": "cz",
    "y": "tu", "z": "x", " ": " ",
}


def human_type(page, text):
    for ch in text:
        lc = ch.lower()
        if lc != " " and random.random() < 0.07 and NEARBY.get(lc):
            wrong = random.choice(NEARBY[lc])
            page.keyboard.type(wrong, delay=55 + random.random() * 90)
            jitter(80, 220)
            page.keyboard.press("Backspace")
            jitter(60, 180)
        page.keyboard.type(ch, delay=55 + random.random() * 110)
        if random.random() < 0.08:
            jitter(180, 550)


# ─── Ad blocking ──────────────────────────────────────────────────────────────

AD_PATTERNS = [
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "googletagmanager.com", "google-analytics.com", "facebook.net", "fbcdn.net",
    "amazon-adsystem.com", "taboola.com", "outbrain.com", "criteo.com",
    "pubmatic.com", "rubiconproject.com", "openx.net", "adsrvr.org",
    "moatads.com", "adnxs.com", "connatix.com", "vidazoo.com", "jwplayer.com",
]


def is_ad(url):
    return any(p in url for p in AD_PATTERNS)


# ─── Classification ───────────────────────────────────────────────────────────

def safe_content(page, tries=4):
    """page.content() that tolerates mid-navigation ('page is navigating') — the
    race that aborted prior runs. Retries, then returns '' rather than raising."""
    for _ in range(tries):
        try:
            return page.content()
        except Exception:
            sleep(700)
    try:
        return page.content()
    except Exception:
        return ""


def classify(html):
    lc = html.lower()
    # Check for actual CF challenge pages first (small, no real content)
    if ("just a moment" in lc or "checking your browser" in lc
            or "access denied" in lc or ("cloudflare" in lc and len(html) < 5000)):
        return "blocked"
    # FPS success — check before turnstile since FPS's own pages embed CF scripts
    if "did not return any matches" in lc or "no results found" in lc:
        return "no_results"
    if len(html) > 8000 and 'class="card"' in lc:
        return "success"
    # Only flag turnstile on actual challenge pages (have __cf_chl or verify-human text)
    if ("verify you are human" in lc or "__cf_chl" in lc
            or ("challenge-platform" in lc and len(html) < 8000)):
        return "turnstile"
    if len(html) > 5000 and "fastpeoplesearch" in lc:
        return "fps_home"
    return "unknown"


def count_cards(html):
    import re
    return len(re.findall(r'class="card["\s]', html))


def is_google_captcha(page):
    """Google's 'unusual traffic' interstitial (reCAPTCHA v2 checkbox)."""
    try:
        html = page.content().lower()
    except Exception:
        return False
    return ("unusual traffic" in html
            or "/sorry/" in page.url
            or "recaptcha" in html and "not a robot" in html)


# ─── Google reCAPTCHA checkbox: try the cheap single-click pass ───────────────

def try_recaptcha_checkbox(page):
    """
    Click the 'I'm not a robot' checkbox. Returns:
      'passed'     - checkbox accepted, interstitial gone
      'escalated'  - image/audio puzzle appeared (need a solver layer)
      'absent'     - no checkbox found
    """
    page.screenshot(path=str(OUT_DIR / "recaptcha-before.png"))
    anchor = page.frame_locator(
        'iframe[src*="recaptcha"][src*="anchor"], iframe[title*="reCAPTCHA"]'
    ).locator("#recaptcha-anchor, .recaptcha-checkbox").first
    try:
        anchor.wait_for(timeout=8000)
    except Exception:
        log("  reCAPTCHA: no checkbox anchor found")
        return "absent"

    log("  reCAPTCHA: checkbox found — clicking (humanized)...")
    jitter(500, 1200)
    anchor.click()           # Camoufox humanizes the cursor path to this click
    jitter(2500, 4000)
    page.screenshot(path=str(OUT_DIR / "recaptcha-after.png"))

    # Did a challenge popup (bframe) appear and become visible?
    challenge = page.frame_locator(
        'iframe[src*="recaptcha"][src*="bframe"], iframe[title*="challenge"]'
    )
    try:
        if challenge.locator("#rc-imageselect, .rc-imageselect").first.is_visible(timeout=4000):
            log("  reCAPTCHA: ESCALATED to image puzzle — needs audio/STT solver")
            return "escalated"
    except Exception:
        pass

    if not is_google_captcha(page):
        log("  reCAPTCHA: checkbox PASSED silently ✓")
        return "passed"
    log("  reCAPTCHA: still on interstitial, no visible puzzle (ambiguous)")
    return "escalated"


# ─── Cloudflare Turnstile (opportunistic — may gate before landing OR after the
# search submit on the /name/ results page, or not appear at all) ──────────────

CF_HOSTS = ("challenges.cloudflare.com",)
RESULTS_SEL = '.card, [class*="card"], #results, .person-card, .people-list'


def _challenge_frames(page):
    """Cloudflare interactive-challenge / Turnstile frames ANYWHERE in the (nested)
    frame tree. page.frames is nesting-aware; page.locator is NOT (it only sees the
    top document) — which is exactly why a Turnstile nested inside FPS's own
    /cdn-cgi/challenge-platform/ iframe was being missed every time."""
    out = []
    for fr in page.frames:
        u = (fr.url or "").lower()
        if any(h in u for h in CF_HOSTS):
            out.append(fr)
    return out


def turnstile_present(page):
    """True if a Cloudflare challenge/Turnstile is gating the page (nested or not)."""
    try:
        if "__cf_chl" in page.url:
            return True
        if (page.title() or "").strip().lower().startswith("just a moment"):
            return True
        if _challenge_frames(page):
            return True
    except Exception:
        pass
    return False


def _frame_rect(fr):
    """Absolute (main-viewport) bounding box of the iframe hosting frame `fr`, or
    None. frame_element()+bounding_box() have NO timeout and BLOCK FOREVER on a
    detaching/cross-origin frame (the post-clearance hang), so skip detached frames
    and only call this on the turnstile widget — never the loaded page's many
    maps/ad/widget frames."""
    try:
        if fr.is_detached():
            return None
        bb = fr.frame_element().bounding_box()
        if bb and bb["width"] > 0 and bb["height"] > 0:
            return bb
    except Exception:
        pass
    return None


def _log_frame_tree(page, tag):
    """Ground-truth dump of frame URLs. URLs ONLY (fr.url is safe) — we do NOT call
    bounding_box() here: on the loaded results page that blocks forever on detaching
    map/ad iframes (the hang)."""
    try:
        frames = page.frames
        log(f"  [frames:{tag}] {len(frames)} frame(s):")
        for fr in frames:
            log(f"     {(fr.url or '')[:100]}")
    except Exception as e:
        log(f"  [frames:{tag}] dump failed: {e!s:.50}")


def handle_turnstile(page, max_wait=70):
    """Click the Cloudflare Turnstile checkbox WHEREVER it is — including nested
    inside FPS's /cdn-cgi/challenge-platform/ iframe.

    Root-cause fix vs. prior attempts: enumerate the FULL frame tree via page.frames
    (nesting-aware, unlike page.locator which only sees the top document), find the
    challenges.cloudflare.com widget frame, take its iframe element's ABSOLUTE
    bounding box, and humanized-coordinate-click the checkbox (left ~30px, vertical
    centre). Success = results render, OR the challenge frame we interacted with
    disappears (CF passed + navigated). Heavily instrumented: dumps the frame tree
    so a miss is never blind. Returns True if cleared.
    """
    start = time.time()
    saw_challenge = False
    empty_streak = 0
    last_dump = 0.0
    last_click = 0.0
    # Hang-proof clearance detection: a network response carrying the CF clearance
    # token (__cf_chl_f_tk, status 200) means we passed. Set via a response listener
    # — an event callback that never blocks, unlike frame/locator introspection.
    cleared = {"v": False}

    def _on_resp(r):
        try:
            if "__cf_chl_f_tk" in r.url and r.status == 200:
                cleared["v"] = True
        except Exception:
            pass

    page.on("response", _on_resp)
    try:
        while time.time() - start < max_wait:
            elapsed = time.time() - start
            # Hang-proof success: CF clearance response arrived.
            if cleared["v"]:
                log(f"  [turnstile] cleared — CF clearance response (~{elapsed:.0f}s)")
                return True
            # Cheap, non-blocking URL signals next.
            try:
                url = page.url
            except Exception:
                url = ""
            if "__cf_chl_f_tk" in url or "_id_" in url:
                log(f"  [turnstile] cleared — clearance/profile URL (~{elapsed:.0f}s): {url[:70]}")
                return True
            # Real results / profile content rendered.
            try:
                if page.locator(RESULTS_SEL).first.is_visible(timeout=250):
                    log(f"  [turnstile] results visible at ~{elapsed:.0f}s — cleared")
                    return True
            except Exception:
                pass

            cfs = _challenge_frames(page)

            if time.time() - last_dump > 8:
                _log_frame_tree(page, f"{elapsed:.0f}s")
                last_dump = time.time()

            if not cfs:
                # We'd interacted with a challenge and now it's gone -> passed.
                if saw_challenge:
                    log(f"  [turnstile] challenge frame gone after click (~{elapsed:.0f}s) — cleared")
                    return True
                # Never saw a challenge. On the /name/ interstitial or a __cf_chl URL
                # it's probably still loading — keep waiting; else nothing to solve.
                on_interstitial = ("/name/" in url) or ("__cf_chl" in url)
                if not on_interstitial:
                    empty_streak += 1
                    if empty_streak >= 4:
                        log(f"  [turnstile] no challenge present (~{elapsed:.0f}s) — clear")
                        return True
                jitter(1500, 2200)
                continue

            # Challenge frame(s) present -> click the widget checkbox. Only the
            # turnstile widget reaches _frame_rect (others are non-CF), and
            # _frame_rect skips detached frames — so no unbounded blocking.
            saw_challenge = True
            empty_streak = 0
            # CLICK COOLDOWN: after a click, do NOT call _frame_rect again for ~12s.
            # Right after a successful click the turnstile frame is attached-but-
            # transitioning, and frame_element()/bounding_box() (no timeout) BLOCK
            # FOREVER on it. During the cooldown we poll only cheap signals (cleared
            # flag, url, frame-gone via fr.url) — which catch the pass — and re-click
            # only if it's genuinely still there after.
            if time.time() - last_click < 12:
                jitter(1500, 2200)
                continue
            target = None
            for fr in cfs:
                bb = _frame_rect(fr)
                if not bb or bb["width"] < 20 or bb["height"] < 20:
                    continue
                if 160 <= bb["width"] <= 540 and 40 <= bb["height"] <= 150:
                    target = bb; break          # the visible "Verify you are human" card
                if target is None:
                    target = bb                 # fallback: any sized CF frame
            if not target:
                log(f"  [turnstile] CF frame(s) present but no usable rect (~{elapsed:.0f}s)")
                jitter(1500, 2200)
                continue
            # Checkbox position: inline widget -> left ~30px; full-page -> left-of-centre.
            if target["width"] > 550:
                cx = target["x"] + target["width"] / 2 - 130 + random.random() * 8
                cy = target["y"] + target["height"] / 2 + (random.random() - 0.5) * 6
            else:
                cx = target["x"] + 30 + random.random() * 6
                cy = target["y"] + target["height"] / 2 + (random.random() - 0.5) * 4
            log(f"  [turnstile] coord-click checkbox ({cx:.0f},{cy:.0f}) in "
                f"{target['width']:.0f}x{target['height']:.0f} iframe (~{elapsed:.0f}s)")
            try:
                page.mouse.move(cx - 80, cy + 55); jitter(140, 320)
                page.mouse.move(cx - 14, cy + 7);  jitter(110, 260)
                page.mouse.move(cx, cy);           jitter(90, 200)
                page.mouse.click(cx, cy)
                last_click = time.time()            # start the no-_frame_rect cooldown
                jitter(7000, 10000)                 # let CF verify + the page advance
            except Exception as e:
                log(f"  [turnstile] coord-click error: {e!s:.50}")
        log(f"  [turnstile] NOT cleared within {max_wait}s")
        _log_frame_tree(page, "final")
        return False
    finally:
        try:
            page.remove_listener("response", _on_resp)
        except Exception:
            pass


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    label = " ".join(x for x in [FIRST, LAST, CITY, STATE] if x)
    log(f'FPS smoke (Camoufox) — "{label}"')
    if PROXY:
        log(f"  proxy: {PROXY['server']}")
    else:
        log("  proxy: NONE (direct from VPS IP)")

    start_display_and_recording()
    log(f"  display: {DISPLAY}  video: {VIDEO_PATH}")

    cam_kwargs = dict(
        headless=False,          # use our Xvfb display (DISPLAY env set above)
        humanize=True,           # human-like cursor movement + click timing
        geoip=False,             # skip proxy geoip validation (causes 502 on some rotations)
        # Pin a normal landscape desktop window. Fixes the long-standing
        # "content shifted right" render (window/viewport mismatch, seen since the
        # VPS) AND the window-vs-screen fingerprint inconsistency: Camoufox centers
        # this window inside a coherent screen (handle_window_size). Clips slightly
        # on the portrait panel — cosmetic only; we manage over SSH.
        window=(1280, 720),
        # Disable Firefox's Enhanced Tracking Protection — ETP blocks the
        # challenges.cloudflare.com iframe, causing 24 postMessage errors and a
        # 23-second delay before api.js even loads. With these off, api.js loads
        # in <1s and the iframe can communicate via postMessage normally.
        firefox_user_prefs={
            "privacy.trackingprotection.enabled": False,
            "privacy.trackingprotection.pbmode.enabled": False,
            "privacy.firstparty.isolate": False,
            "privacy.partition.network_state.connection_with_proxy": False,
            "network.http.referer.disallowCrossSiteRelaxingDefault": False,
        },
    )
    # OS fingerprint. Default: spoof Windows (the long-standing config). With
    # NATIVE_FP=1, drop the spoof so Camoufox uses the host's native OS (macOS
    # locally). Tests whether the Windows-UA-on-Apple-GPU mismatch is the
    # inconsistency Google catches. Non-destructive — Windows path is the default.
    if NATIVE_FP:
        log("  fingerprint: NATIVE (no os spoof — host OS)")
    else:
        cam_kwargs["os"] = ["windows"]   # spoof a Windows fingerprint
        log("  fingerprint: Windows spoof (os=['windows'])")

    if PROXY:
        cam_kwargs["proxy"] = PROXY

    final_class = "unknown"
    with Camoufox(**cam_kwargs) as browser:
        # no_viewport=True so Playwright skips Browser.setDefaultViewport, whose
        # newer `isMobile` field the Camoufox 0.4.11 Firefox juggler rejects.
        context = browser.new_context(no_viewport=True)

        def route(r):
            url = r.request.url
            if is_ad(url):
                return r.abort()
            if "fastpeoplesearch" in url and r.request.resource_type == "media":
                return r.abort()
            return r.continue_()

        context.route("**/*", route)
        page = context.new_page()

        # Suppress uncaught JS errors so they don't crash Playwright's Firefox driver.
        # Firefox sends pageError events without a location field on some pages (e.g.
        # Google's 429 page), which triggers a TypeError in Playwright's Node.js internals
        # and kills the connection. window.onerror returning true prevents the propagation.
        page.add_init_script("window.onerror = function() { return true; };")

        page.on("console", lambda m: log(f"  [browser:err] {m.text[:120]}")
                if m.type == "error" else None)

        google_blocked = {"v": False}

        def on_resp(r):
            u = r.url
            if "/sorry/" in u and "google.com" in u and r.status in (200, 429):
                google_blocked["v"] = True
            if "fastpeoplesearch" in u or "cloudflare" in u or "turnstile" in u or "/sorry/" in u:
                log(f"  [http] {r.status} {u[:110]}")
        page.on("response", on_resp)

        try:
            # ── 0. Verify egress IP (confirms proxy is routing) ───────────────
            if PROXY:
                try:
                    page.goto("https://api.ipify.org?format=text", wait_until="domcontentloaded", timeout=10000)
                    egress_ip = page.inner_text("body").strip()
                    log(f"  egress IP (via proxy): {egress_ip}")
                except Exception as e:
                    log(f"  egress IP check failed: {e}")

            # ── 1-2. Google (skippable: Google reliably 429s automation/proxy IPs,
            # and direct-to-FPS-with-referer works on its own → SKIP_GOOGLE=1) ────
            already_on_fps = os.environ.get("SKIP_GOOGLE") == "1"
            if already_on_fps:
                log("[1/6] SKIP_GOOGLE=1 — going direct to FPS with Google referer")
            else:
                # ── 1. Google ────────────────────────────────────────────────
                log("[1/6] Google...")
                page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=30000)
                log(f'  title: "{page.title()}"')
                jitter(700, 1400)
                for sel in ['button:has-text("Accept all")', 'button:has-text("I agree")']:
                    btn = page.locator(sel).first
                    if btn.count() > 0:
                        btn.click()
                        jitter(400, 800)
                        break

                # ── 2. Type search ───────────────────────────────────────────
                log("[2/6] Typing search...")
                sb = page.locator('textarea[name="q"], input[name="q"]').first
                sb.wait_for(timeout=10000)
                sb.click()
                jitter(200, 500)
                human_type(page, "fast people search")
                jitter(400, 900)
                page.keyboard.press("Enter")
                # Google SERP is JS-rendered — wait for result container.
                try:
                    page.wait_for_selector(
                        "#search, #rso, .g, [data-async-context]",
                        timeout=20000,
                        state="attached",
                    )
                except Exception as google_err:
                    log(f"  Google SERP failed ({google_err!s:.80}) — going direct to FPS with Referer")
                    already_on_fps = True
                jitter(1200, 2000)

            if already_on_fps:
                # ── 3-4 skipped: navigate directly to FPS ────────────────────
                log("[3/6] Skipped (Google blocked) — going direct to FPS.")
                log("[4/6] Direct FPS navigation with Google Referer...")
                fps_url = "https://www.fastpeoplesearch.com/"
                page.goto(
                    fps_url,
                    referer="https://www.google.com/search?q=fast+people+search",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                jitter(1500, 3000)
                log(f'  landed: {page.url} | title: "{page.title()}"')
            else:
                # ── 3. Handle Google reCAPTCHA interstitial if present ───────
                if is_google_captcha(page):
                    log("[3/6] Google 'unusual traffic' interstitial detected.")
                    page.content() and (OUT_DIR / "google-captcha.html").write_text(page.content(), encoding="utf-8")
                    result = try_recaptcha_checkbox(page)
                    if result != "passed":
                        log(f"  reCAPTCHA not cleared ({result}) — stopping for review.")
                        page.screenshot(path=str(OUT_DIR / "fps-screenshot.png"))
                        (OUT_DIR / "fps-results.html").write_text(page.content(), encoding="utf-8")
                        final_class = f"google_recaptcha_{result}"
                        context.close()
                        return final_class
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    jitter(1000, 2000)
                else:
                    log("[3/6] No Google interstitial — results loaded directly.")

                fps_count = page.locator('a[href*="fastpeoplesearch.com"]:visible').count()
                log(f"  FPS links in results: {fps_count}")
                if fps_count == 0:
                    log("  ERROR: no FPS links in results — saving page for review")
                    page.screenshot(path=str(OUT_DIR / "fps-screenshot.png"))
                    (OUT_DIR / "google-results.html").write_text(page.content(), encoding="utf-8")
                    final_class = "no_fps_links"
                    context.close()
                    return final_class

                # ── 4. Scroll + click the FPS result ─────────────────────────
                log("[4/6] Scroll past -> back -> click FPS result...")
                page.keyboard.press("Escape")
                jitter(300, 500)
                page.mouse.wheel(0, 500); jitter(600, 1000)
                page.mouse.wheel(0, 300); jitter(500, 900)
                page.mouse.wheel(0, -400); jitter(500, 900)

                link = page.locator('a[href*="fastpeoplesearch.com"]:visible').first
                fps_url = link.get_attribute("href") or "https://www.fastpeoplesearch.com/"
                log(f'  target: {fps_url}')

                # Try a direct click first; if it times out fall back to goto with Referer
                try:
                    link.click(timeout=12000)
                    page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception as click_err:
                    log(f"  direct click failed ({click_err!s:.80}), falling back to goto+Referer")
                    page.goto(
                        fps_url,
                        referer="https://www.google.com/search?q=fast+people+search",
                        wait_until="domcontentloaded",
                        timeout=20000,
                    )
                jitter(1500, 3000)
                log(f'  landed: {page.url} | title: "{page.title()}"')

            # ── 5. FPS Turnstile (may gate the landing page) ──────────────────
            landing_class = classify(safe_content(page))
            log(f"  landing classification: {landing_class}")
            if landing_class in ("turnstile", "blocked") or turnstile_present(page):
                log("[5/6] Turnstile/challenge on landing — solving...")
                handle_turnstile(page)
                page.screenshot(path=str(OUT_DIR / "turnstile-landing.png"))
                log(f"  post-landing-turnstile: {page.url[:80]} | class={classify(safe_content(page))}")
            else:
                log("[5/6] No Turnstile on landing — continuing.")

            # ── 6. Fill FPS search form (real selectors; Enter selects + searches)
            log("[6/6] FPS search form...")
            name_in = page.locator('#search-name-name, input[name="name"]').first
            if name_in.count() > 0:
                name_in.click(); jitter(200, 500)
                human_type(page, f"{FIRST} {LAST}")
                jitter(300, 700)
                if CITY or STATE:
                    loc = page.locator(
                        '#search-name-address, input.autocomplete-city, '
                        'input[name="address"], input[placeholder*="City" i]'
                    ).first
                    if loc.count() > 0:
                        loc.click(); jitter(150, 400)
                        human_type(page, ", ".join(x for x in [CITY, STATE] if x))
                        # City/state is a searchable dropdown: pressing Enter while a
                        # match is showing SELECTS it AND auto-runs the search (one
                        # step). Let the acplace autocomplete populate first.
                        jitter(1200, 1800)
                        log("  city/state dropdown — Enter to select + search")
                        loc.press("Enter")
                    else:
                        name_in.press("Enter")
                else:
                    name_in.press("Enter")

                def _left_home(url):
                    return "/name/" in url or url.rstrip("/") != "https://www.fastpeoplesearch.com"

                # The FPS search is JS-driven and can take ~15-20s to reach /name/.
                # Wait generously for it to leave home before deciding anything.
                try:
                    page.wait_for_url(_left_home, timeout=30000)
                except Exception:
                    pass

                # Fallback: if STILL on home, the Enter didn't commit a match — click
                # the NAME form's real submit button (scoped, never the logo).
                if not _left_home(page.url):
                    try:
                        submit = page.locator(
                            '#form-search-name button.search-form-button-submit, '
                            '#form-search-name button[type="submit"]'
                        ).first
                        if submit.count() > 0:
                            log("  still on home — clicking real submit button")
                            submit.click(timeout=8000)
                            page.wait_for_url(_left_home, timeout=20000)
                    except Exception as e:
                        log(f"  submit fallback: {e!s:.60}")

                # Solve the (possibly nested) Turnstile gating /name/. UNCONDITIONAL:
                # handle_turnstile polls, is navigation-robust, and returns fast if
                # results already show. Do NOT gate on page.content() — it throws
                # while the page is mid-navigation (that was the prior abort).
                log("  running Turnstile solver (post-search)...")
                handle_turnstile(page)
                try:
                    page.wait_for_selector(RESULTS_SEL, timeout=10000)
                except Exception:
                    pass
                jitter(2000, 3000)
                log(f"  final url: {page.url}")
            else:
                log("  no search form found — classifying current page")

            html = safe_content(page)
            final_class = classify(html)
            cards = count_cards(html)
            page.screenshot(path=str(OUT_DIR / "fps-screenshot.png"))
            (OUT_DIR / "fps-results.html").write_text(html, encoding="utf-8")

            log("")
            log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log(f"Classification: {final_class.upper()}")
            if final_class == "success":
                log(f"✅ ~{cards} result cards")
            elif final_class == "fps_home":
                log("⚠  Still on FPS homepage — form submission may have failed")
            elif final_class == "turnstile":
                log("⚠  Turnstile not bypassed")
            elif final_class == "blocked":
                log("✗  Hard blocked")
            elif final_class == "no_results":
                log("~  No results for query")
            else:
                log(f"?  Unknown — html length: {len(html)}")
            log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        except Exception as e:
            log(f"ERROR: {e}")
            try:
                page.screenshot(path=str(OUT_DIR / "fps-screenshot.png"))
                (OUT_DIR / "fps-error.html").write_text(safe_content(page), encoding="utf-8")
            except Exception:
                pass
            final_class = "error"
        finally:
            try:
                context.close()
            except Exception:
                pass

    stop_recording()
    return final_class


if __name__ == "__main__":
    try:
        result = run()
    finally:
        flush_log()
    log(f"DONE: {result}")
    flush_log()
