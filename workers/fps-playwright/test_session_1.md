  Run 1 — Basic Playwright, no proxy, no stealth

  Result: BLOCKED. Script landed on FPS homepage, classified as blocked, bailed immediately.

  Didn't try to interact with the Turnstile widget that was clearly visible in the video.

  Run 2 — Added video recording + detailed logging

  Result: Same BLOCKED classification, but the video revealed something important — FPS was

  actually loading a Cloudflare Turnstile "Verify you are human" checkbox, not a hard IP ban.

  The page showed "Loading Search Results..." styled in the FPS layout. Logs confirmed 403 from

  FPS → CF Turnstile loaded → script bailed without clicking. Key log lines: 403

  [https://www.fastpeoplesearch.com/](https://www.fastpeoplesearch.com/) → challenges.cloudflare.com/turnstile/... loaded → 401 on

  Private Access Token → title: "Just a moment...".

  Run 3 — Added stealth plugin (playwright-extra), human typing with mistypes, scroll behavior,

  bezier mouse, ad blocking, FlameProxies proxy

  Result: 429 from Google before we even got to FPS. FPS links in results: 0. Root cause:

  --disable-web-security flag (which I added and shouldn't have flagged after the fact) combined

  with playwright-extra changing request behavior, possibly triggering Google's bot detection.

  The FlameProxies proxy was confirmed active in the logs.

  Run 4 — Stripped stealth + proxy, kept human behavior, fixed --disable-web-security, added

  Turnstile click attempt

  Result: 429 from Google again. FPS links: 0. Google is blocking the Hetzner datacenter IP on

  search — same error, same point in the flow. The Turnstile click code was never reached.

  ---

  Pattern: Google is the consistent blocker. We got through Google successfully exactly once

  (Run 1 and Run 2 — before any extra layers), hit the FPS Turnstile, but bailed. Every run

  since has failed at Google before reaching FPS. The Hetzner IP is the most likely culprit for

  the Google 429 — it may have accumulated rate limit state from our repeated runs in the same

  session.

  Open questions:

  1. Is Google rate-limiting the Hetzner IP temporarily from our repeated runs, or is it

  permanently flagged?

  2. Should we skip Google entirely and set the Referer header manually when navigating to FPS?

  3. Should we re-introduce FlameProxies (residential IP clears both Google and FPS)?