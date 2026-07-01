#!/usr/bin/env python3
"""
Screen/window probe — ground truth for the long-standing "content shifted right"
rendering issue (seen since the VPS, independent of the portrait monitor).

Reports what Camoufox actually presents for window vs. screen geometry, so we can
pin window/screen to a coherent landscape desktop instead of guessing. Read-only.
Run in the interactive desktop session (real iGPU/window). Writes out/screen.json.
"""
import json
import os
from pathlib import Path

from camoufox.sync_api import Camoufox

OUT = Path(os.environ.get("OUT_DIR", str(Path(__file__).parent / "out")))
OUT.mkdir(parents=True, exist_ok=True)

JS = r"""
() => ({
  innerWidth: window.innerWidth, innerHeight: window.innerHeight,
  outerWidth: window.outerWidth, outerHeight: window.outerHeight,
  screenX: window.screenX, screenY: window.screenY,
  devicePixelRatio: window.devicePixelRatio,
  screen: {
    width: screen.width, height: screen.height,
    availWidth: screen.availWidth, availHeight: screen.availHeight,
    orientation: (screen.orientation && screen.orientation.type) || null,
  },
  scrollMaxX: window.scrollMaxX, scrollMaxY: window.scrollMaxY,
  documentWidth: document.documentElement.scrollWidth,
  visualViewport: window.visualViewport ? {
    width: window.visualViewport.width, height: window.visualViewport.height,
    scale: window.visualViewport.scale,
    offsetLeft: window.visualViewport.offsetLeft,
  } : null,
  ua: navigator.userAgent, platform: navigator.platform,
})
"""


def main():
    results = {}
    # Probe both the current (default) config and an explicit landscape pin, so we
    # can see whether pinning window/screen actually corrects the geometry.
    # Camoufox auto-coheres the screen fingerprint around a user-specified `window`
    # (handle_window_size), so we only pin `window` and let it center/size the screen.
    variants = [
        ("default", dict(headless=False, humanize=False, geoip=False, os=["windows"])),
        ("pinned",  dict(headless=False, humanize=False, geoip=False, os=["windows"],
                         window=(1280, 720))),
    ]
    for label, kw in variants:
        try:
            with Camoufox(**kw) as b:
                ctx = b.new_context(no_viewport=True)
                pg = ctx.new_page()
                pg.goto("about:blank")
                data = pg.evaluate(JS)
        except Exception as e:
            data = {"error": f"{type(e).__name__}: {e}"}
        results[label] = data
        print(f"[{label}] {json.dumps(data)[:400]}")
    (OUT / "screen.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"WROTE {OUT / 'screen.json'}")


if __name__ == "__main__":
    main()
