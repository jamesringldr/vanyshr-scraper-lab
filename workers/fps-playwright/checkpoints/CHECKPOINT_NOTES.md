# FPS scraper checkpoints

## smoke_CHECKPOINT_2026-06-30_FULL-SUCCESS-no-hang.py  ← CURRENT BEST

**Full pipeline works end-to-end, automated, clean exit. Use this as the baseline.**
Verified on serv-01 (home IP, no proxy, `SKIP_GOOGLE=1`): direct nav → form
Enter-search → nested-iframe Turnstile auto-solve → **clean success exit** →
centered render → `Classification: SUCCESS` / `DONE: success`, screenshot saved.

Adds over the prior checkpoint (fixes its known hang):
- **Post-clearance hang FIXED** via a click-cooldown: after clicking the Turnstile
  checkbox, do NOT call `_frame_rect`/`frame_element().bounding_box()` for ~12s
  (those have no timeout and block forever on the attached-but-transitioning frame).
  During cooldown, poll only cheap signals (network `__cf_chl_f_tk` clearance flag,
  `page.url`, frame-gone via `fr.url`). Re-click only if still present after.
- `_log_frame_tree` dumps URLs only; `_frame_rect` skips `is_detached()` frames.
- Clearance detected via a `page.on("response")` flag (`__cf_chl_f_tk` 200).
- KNOWN intermittent (NOT in this file): Playwright/Firefox driver crash on a
  page error with no `location` (`pageError.location.url` undefined) — rare, retry.
- Next frontier: summary → click specific person → **detailed `_id_` profile** page.

---


## smoke_CHECKPOINT_2026-06-30_turnstile-solve+centering.py

**The closest-to-working version. Fall back to this if later changes go sideways.**

Verified on serv-01 (Beelink box, home residential IP, no proxy, `SKIP_GOOGLE=1`,
direct-to-FPS with Google referer):

### What WORKS at this checkpoint
- Direct FPS navigation passes Cloudflare (fingerprint + residential IP trusted).
- Real-selector form fill: `#search-name-name` + `#search-name-address`, then **Enter**
  in the city/state field selects the dropdown match and auto-runs the search → `/name/`.
- **Cloudflare Turnstile auto-solved** (the hard win): the widget is a NESTED iframe
  (`challenges.cloudflare.com/.../turnstile/...` inside FPS's `/cdn-cgi/challenge-platform/`
  iframe). Found via `page.frames` (nesting-aware; `page.locator` could not see it),
  rect via `frame_element().bounding_box()`, humanized coordinate-click at left+~30px /
  vertical-center. Clearance granted (`?__cf_chl_f_tk=...`) → reaches the real profile.
  Confirmed automated 2/2 runs.
- **Window/screen centering fixed**: `window=(1280, 720)` in cam_kwargs — Camoufox
  centers it in a coherent screen (handle_window_size). Fixes the long-standing
  "content shifted right" render AND the window-vs-screen fingerprint mismatch.
- UTF-8 stdout (`sys.stdout.reconfigure`) — no more `charmap` crash on the log banner.
- `safe_content()` wrapper around `page.content()` — survives mid-navigation reads.

### KNOWN BUG in this checkpoint (what the NEXT change fixes)
- **Post-clearance HANG.** After the Turnstile passes, the FPS results page loads many
  iframes (Google Maps embed, clym, ads, CF telemetry). `_frame_rect` /
  `_log_frame_tree` call `frame_element().bounding_box()` on those frames — and those
  calls have NO timeout in Playwright, so one detaching/cross-origin frame blocks
  forever. The loop never reaches the `__cf_chl_f_tk` URL check and `max_wait` never
  fires (only checked between iterations). Result: the run hangs (browser stays alive)
  instead of exiting clean with `success`, so no screenshot/artifact is saved.
- Not built yet: the summary-page → click-the-specific-person → **detailed profile**
  step (user had to click it manually). Next frontier.

### Next change (working copy = smoke.py)
Make the solver hang-proof: (1) detect clearance via a network-response flag
(`__cf_chl_f_tk` 200) checked first each loop; (2) `_frame_rect`/`_log_frame_tree`
skip `is_detached()` frames, only rect the `/turnstile/` widget, dump URLs only.
