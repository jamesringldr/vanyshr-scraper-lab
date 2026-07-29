#!/usr/bin/env python3
"""
WebGL fingerprint probe — what does Camoufox actually present to a page?

The Beelink box exists on one premise: Cloudflare reads the WebGL UNMASKED_RENDERER
and a real Intel iGPU renderer string beats a software/synthetic one. But Camoufox
spoofs fingerprints by default — so we must verify empirically whether the REAL
Intel(R) UHD renderer reaches the page, or whether Camoufox overrides it.

MUST run in the interactive desktop session (real GPU). Launched over SSH it gets a
software renderer and the result is meaningless.

Runs two variants and writes both to out/webgl.json:
  - native : no os spoof (host = Windows, real iGPU passthrough hoped-for)
  - winspoof: os=["windows"] (the smoke.py default) — does the spoof clobber renderer?

Usage: python webgl_probe.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from camoufox.sync_api import Camoufox

OUT_DIR = Path(os.environ.get("OUT_DIR", str(Path(__file__).parent / "out")))
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "webgl.json"

PROBE_JS = r"""
() => {
  const out = { ok: false };
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
    if (!gl) { out.error = 'no webgl context'; return out; }
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    out.vendor          = gl.getParameter(gl.VENDOR);
    out.renderer        = gl.getParameter(gl.RENDERER);
    out.unmaskedVendor  = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : null;
    out.unmaskedRenderer= dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null;
    out.version         = gl.getParameter(gl.VERSION);
    out.shadingLang     = gl.getParameter(gl.SHADING_LANGUAGE_VERSION);
    out.ua              = navigator.userAgent;
    out.platform        = navigator.platform;
    out.hw              = navigator.hardwareConcurrency;
    out.ok = true;
  } catch (e) { out.error = String(e); }
  return out;
}
"""


def probe(label, cam_kwargs):
    with Camoufox(**cam_kwargs) as browser:
        # no_viewport=True so Playwright skips Browser.setDefaultViewport, whose
        # newer `isMobile` field this Camoufox Firefox build rejects.
        context = browser.new_context(no_viewport=True)
        page = context.new_page()
        page.goto("about:blank")
        data = page.evaluate(PROBE_JS)
        data["label"] = label
        return data


def main():
    results = {"ts": datetime.now(timezone.utc).isoformat(), "python": sys.executable, "runs": []}

    variants = [
        ("native",   dict(headless=False, humanize=False, geoip=False)),
        ("winspoof",  dict(headless=False, humanize=False, geoip=False, os=["windows"])),
    ]
    for label, kwargs in variants:
        try:
            r = probe(label, kwargs)
        except Exception as e:
            r = {"label": label, "ok": False, "error": f"{type(e).__name__}: {e}"}
        results["runs"].append(r)
        print(f"[{label}] {json.dumps(r)[:300]}")

    OUT_FILE.write_text(json.dumps(results, indent=2))
    print(f"WROTE {OUT_FILE}")


if __name__ == "__main__":
    main()
