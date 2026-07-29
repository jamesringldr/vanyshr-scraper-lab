# **Advanced Bot Detection Bypass: The 2026 State of the Art**

Alright. Let's skip the basics. You already know `navigator.webdriver`, `puppeteer-extra-plugin-stealth`, and `undetected-chromedriver` are dead. They've been dead since 2024. Here's the realpicture, drawn from the front lines of the arms race as it stands right now — June 2026.

---

## **I. THE DETECTION PIPELINE: What You're Actually Up Against**

Both Cloudflare and DataDome operate a **layered filtering pipeline** at the edge. This is the architecture you need to understand before any strategy makes sense:

text

```
Request → [1] IP/ASN Reputation → [2] TLS/JA4 Fingerprint → [3] HTTP/2 Frame Analysis → [4] HTTP Header Consistency → [5] JS Challenge (Turnstile/Device Check) → [6] Behavioral Analysis → Origin

```

A request can fail at **any** layer. Fail at layer 1, and your perfect Chrome fingerprint at layer 2 never even gets evaluated. This is why single-layer solutions always fail.

Let me break down each layer with what actually works in 2026.

---

## **II. LAYER 1 — IP & ASN Reputation (The Gatekeeper)**

This is the cheapest, most decisive check. Cloudflare maintains an ASN-indexed database. Known datacenter ASNs (AWS AS16509, GCP AS15169, Azure AS8075, OVH, DigitalOcean, Hetzner, Vultr) are **presumptively guilty**. Your request from one of these ASNs is flagged before TLS negotiation even completes.

**What works:** Residential IPs. Specifically, residential proxies with a **minimum 10-minute sticky session**. Mobile residential proxies (4G/5G) perform even better because carrier-grade NAT creates natural IP churn that mirrors real user behavior.

**Critical detail:** `cf_clearance` cookies are **bound to the IP that solved the challenge**. If you solve a Turnstile challenge on one IP and then rotate to a new IP, the cookie is worthless. Your entire session — authentication, page navigation, every XHR — must happen on the same sticky IP. This is why `FlareSolverr` and similar cookie-farm approaches fail at scale.

**Accept-Language must match the IP's geography.** A US residential IP sending `de-DE,de;q=0.9` is an immediate signal. This is one of the few high-impact fixes that costs nothing.

---

## **III. LAYER 2 — TLS/JA4 Fingerprinting (What Replaced JA3)**

JA3 is obsolete. JA4, released by FoxIO in 2023, hashes TLS 1.3 ClientHello fields: TLS version, cipher suites (ordered), extensions (ordered), ALPN values, signature algorithms, and supported curves. The output is a deterministic fingerprint like `t13d1516h2_8daaf6152771_b1ff8ab2d16f`.

Real Chrome 131 produces one JA4 hash. Real Firefox 132 produces another. Python's `requests` (urllib3 + OpenSSL) produces a ClientHello that **no real browser generates** — the cipher suite ordering and extension list don't match Chrome or Firefox.

**Detection happens before HTTP headers are even parsed.** This means `requests`, `aiohttp`, default `httpx`, and every library built on system OpenSSL is trivially detectable regardless of how well you set your headers.

### **The Post-Quantum TLS Kill Shot (NEW in 2026)**

This is the biggest development of the past 12 months and **most senior engineers still haven't heard about it.**

By Q2 2026, **57.4% of all browser-initiated connections include an** `X25519MLKEM768` **key share** in the ClientHello. Chrome has sent this by default since Chrome 131 (April 2024). Firefox followed in November 2024. Apple joined October 2025. Akamai made post-quantum key exchange **mandatory for all connections as of January 31, 2026.**

A ClientHello claiming Chrome 131 without `X25519MLKEM768` is a **binary detection signal**. No ML needed. No behavioral analysis. It's a direct mismatch between the claimed User-Agent and the TLS handshake that can be checked before any HTTP traffic flows.

Two named CVEs dropped in 2026 for Go's `uTLS` library (the TLS stack behind `tls-client` and many Go scrapers):

- **CVE-2026-26995**: affects uTLS v1.6.0 through v1.8.1
- **CVE-2026-27017**: affects uTLS v1.6.0 through v1.8.0

Tools pinning to `HelloChrome_120` (pre-PQ) have been **detectable for over two years** and no one realized it until the CVEs dropped.

**The fix:** Upgrade uTLS to **v1.8.2+** and switch to `HelloChrome_131` or later. Verify your ClientHello includes `X25519MLKEM768` in the `key_shares` extension. If you only see `X25519`, you're exposed.

---

## **IV. LAYER 3 — HTTP/2 Frame Fingerprinting**

Browsers emit HTTP/2 frames in a specific, deterministic sequence. Chrome 124 sends `SETTINGS` with specific values, followed by `WINDOW_UPDATE`, then `HEADERS` with a specific pseudo-header order: `:method`, `:authority`, `:scheme`, `:path`.

Python's `httpx` (with HTTP/2 enabled) sends different SETTINGS values, omits the PRIORITY frame Chrome always sends, and pseudo-headers arrive in **alphabetical order** rather than Chrome's fixed order. Cloudflare cross-references this against the claimed User-Agent.

**The fix:** Use `curl_cffi` with `impersonate="chrome124"` (currently the most battle-tested profile). It links against a modified BoringSSL that reproduces Chrome's exact cipher suite ordering, extension list, ALPN values, and HTTP/2 frame sequencing. The JA4 hash from `curl_cffi` impersonating Chrome 124 is **byte-for-byte identical** to real Chrome 124.

`curl_cffi` also auto-orders headers to match Chrome's sequence (`Host`, `Connection`, `sec-ch-ua`, ... `Accept-Language`). If you add custom headers, append them to the end — never insert mid-sequence.

---

## **V. LAYER 4 — Header Consistency & Sec-CH-UA**

The `sec-ch-ua` headers, Client Hints, and User-Agent must form a **coherent, self-consistent identity**. A User-Agent claiming Chrome 130 on Linux with `sec-ch-ua-platform: "Windows"` is an immediate fail. Same for mismatched `sec-ch-ua` brand versions.

The `Accept-Language` header should match the proxy's geographic origin (already covered in Layer 1). `sec-ch-ua-mobile` must be correct for the platform. `sec-ch-ua-full-version-list` should exist and be internally consistent with the `sec-ch-ua` brands.

---

## **VI. LAYER 5 — JavaScript Challenges (Turnstile & Device Check)**

If your request survives layers 1–4 but scores in the suspicious range, you get served a JavaScript challenge.

### **Cloudflare Turnstile**

A JS payload runs in the browser, computing a token from: Canvas fingerprint hash, WebGL renderer string, audio context fingerprint, `navigator` property enumeration (40+ properties), and timing measurements. The token is submitted via XHR. **No pure HTTP client can solve this.** You need a real browser.

### **DataDome Device Check (NEW: Three-Layer VM Obfuscation)**

As of February 2026, DataDome deployed **three-layer obfuscation** on their client-side detection:

1. **VM Obfuscation (NEW):** Detection logic is compiled to a **custom bytecode** executed by a proprietary virtual machine running in the browser. The original source never ships. Each deployment cycle **remaps all opcodes** (0x1F becomes 0x7A), restructures the interpreter internals, and changes the bytecode layout. There is no public specification, no documentation, and no existing reverse-engineering tooling for this VM.
2. **Dynamic Regeneration:** The entire protection stack (including the VM) rebuilds on a regular deployment schedule. Opcodes, encryption keys, variable names, and code structure all change. By the time you reverse-engineer one version, it's obsolete.
3. **WebAssembly Compilation:** Critical detection logic is compiled to WASM binary, which resists traditional JavaScript static analysis.

This is an **economic equation**: the cost to reverse-engineer exceeds the useful lifetime of any single version.

**IMPORTANT for DataDome specifically:** If you're not sending the `datadome` cookie, each session gets exactly **one request** before being challenged. This is a dead giveaway — real users maintain session cookies across requests. You must preserve and echo back the DataDome cookie between requests.

---

## **VII. LAYER 6 — Behavioral Analysis (Enterprise Bot Management)**

Cloudflare Enterprise and DataDome with behavioral tracking continuously sample: mouse movement (acceleration curves, not just coordinates), scroll velocity and jank patterns, click timing and precision, keystroke dynamics, and page interaction chronology.

A headless browser that loads a page and immediately scrolls linearly with pixel-perfect click precision is flagged within seconds. The detection operates in C++ layer, not JavaScript — so JS property overrides like `selenium-stealth` are invisible to it.

**What works (partially):** `rebrowser-playwright` (formerly `patchright`) patches the `Runtime.enable` CDP leak — the primary signal Akamai, DataDome, and Cloudflare use to detect automation via the Chrome DevTools Protocol. This is the `navigator.webdriver` of 2026: a single CDP message that announces "I am automated." `rebrowser-playwright` suppresses it.

For behavioral simulation, you need: non-linear mouse movements with natural acceleration/deceleration curves (Bezier paths, not linear), randomized inter-action delays following a human-like distribution (not uniform random), scrolling patterns that include micro-pauses and overshoot corrections, and realistic page dwell times before interactions begin.

---

## **VIII. THE PRODUCTION-GRADE HYBRID ARCHITECTURE**

The winning pattern for 2026 production scraping is a **two-tier hybrid**:

### **Tier 1:** `curl_cffi` **for Bulk Requests (Cheap & Fast)**

- Residential proxy with sticky sessions (10+ min)
- `curl_cffi` with `impersonate="chrome124"` (bypasses layers 1-4)
- `Accept-Language` matched to proxy geo
- ~85-93% success rate on CF Pro + Bot Fight Mode
- Handles all data extraction once session is established

### **Tier 2:** `rebrowser-playwright` **for Challenge Resolution (Expensive, Used Sparingly)**

- Only invoked when a Managed Challenge (Turnstile/Device Check) is detected
- Solves the JS challenge in a real browser with CDP leak patches
- Extracts `cf_clearance` + `datadome` cookies
- Hands cookies back to Tier 1 for continued scraping
- One browser session can establish clearance for hundreds of `curl_cffi` requests

### **Critical Integration Details:**

- The User-Agent in Playwright must **exactly match** the `impersonate` profile used by `curl_cffi`
- JA4 hash, HTTP/2 fingerprint, and UA string must form a single coherent identity
- Cookie jar is shared and IP-locked — never rotate IPs mid-session
- When `cf_clearance` expires, detect the challenge page, switch back to Tier 2, re-solve, resume

---

## **IX. WHAT'S COMING: Cloudflare PACT Protocol**

Announced June 2026, **PACT** (Private Access Control Tokens) is Cloudflare's answer to the AI agent problem. Sites that have established user trust (browsers, e-commerce platforms) issue anonymous "personhood" tokens. Other sites can verify these tokens without CAPTCHAs or browser fingerprinting.

Google Chrome, Microsoft Edge, Mozilla Firefox, and Shopify have all signed on as development partners. The protocol will be submitted for standardization.

**Why this matters:** PACT fundamentally changes the game. Bots won't just be fighting fingerprinting — they'll be fighting a **cryptographic identity system** backed by browser vendors. A scraping tool that can't produce a valid personhood token will be trivially distinguishable. The architecture hasn't been published yet, but this represents the next frontier of the arms race.

---

## **X. REALITY CHECK: When to Walk Away**

Some deployments are genuinely not worth attacking:


| **Protection Level**       | **Best Strategy**                                | **Max Success Rate** |
| -------------------------- | ------------------------------------------------ | -------------------- |
| CF Free/Pro                | DC proxy + curl_cffi                             | 60-75%               |
| CF Pro + Bot Fight         | Residential + curl_cffi                          | 85-93%               |
| CF Business + Turnstile    | Residential + rebrowser-playwright (per request) | 70-85%               |
| CF Enterprise + Bot Mgmt   | Mobile residential + rebrowser + behavioral sim  | 30-60%               |
| CF Enterprise + Custom WAF | **Don't scrape — use API or partnership**        | <10%                 |


If you see Enterprise Bot Management combined with per-IP rate limiting (3-5 requests per residential IP), custom WAF rules, mandatory login + 2FA + device binding — the economics of scraping collapse. At that point you're better off negotiating API access, buying the data, or finding an alternative source.

---

## **Key Tools Reference (2026)**


| **Tool**                         | **What It Solves**                       | **Status**                                     |
| -------------------------------- | ---------------------------------------- | ---------------------------------------------- |
| `curl_cffi`                      | TLS/JA4 + HTTP/2 impersonation           | ✅ Active, battle-tested                        |
| `tls-client` (Go)                | TLS impersonation for Go stacks          | ⚠️ Upgrade to v1.8.2+ for PQ support           |
| `rebrowser-playwright`           | CDP leak patching for browser automation | ✅ Active, drop-in Playwright replacement       |
| `patchright`                     | Same as rebrowser, alternate fork        | ✅ Active                                       |
| `puppeteer-extra-plugin-stealth` | JS property overrides                    | ❌ Dead — covers ~17 of 40+ detection vectors   |
| `undetected-chromedriver`        | Chromedriver patches                     | ❌ Dead — JA4 leak at TLS layer                 |
| `cloudscraper`                   | Legacy challenge solver                  | ❌ Dead — Cloudflare moved to Turnstile in 2023 |
| `FlareSolverr`                   | Cookie farming                           | ❌ Dead — cookies bind to solver IP             |




---

## **XI. FPS-SPECIFIC — What Vanyshr PROVED + Remaining Keys (2026-06-30)**

Target: **fastpeoplesearch.com** = **Cloudflare (Turnstile / "Security Challenge" / new `/bot-check-submit`) + DataDome** (two stacked layers, confirmed via raw `curl` headers: `Cf-Mitigated: challenge` at the edge; `js.datadome.co` in-page).

### What we EMPIRICALLY validated (matches this doc)
- **The two-tier hybrid (Section VIII) works on FPS.** Tier 2 (Camoufox) solves CF+DataDome once -> harvest `cf_clearance`+`datadome`+`__cf_bm`+UA -> Tier 1 (`curl_cffi` `impersonate="firefox135"`) replays them -> **HTTP 200 with the full real `/name/` record, no browser, ~1s/req.**
- **TLS is the gate, decisively.** Same cookies + same IP + same UA: **plain `curl` -> 403** (curl's JA3/JA4), **`curl_cffi` firefox135 -> 200**. The ONLY difference was the TLS handshake.
- **`cf_clearance` is IP-bound** (Layer 1) — confirmed; the box's residential IP must stay constant.
- **DataDome cookie must be echoed** — we harvest + send it; matches the "one request without the cookie" rule.

### Why Camoufox is the right Tier-2 minter (resolves our patchright failure)
patchright-**Edge/Chrome** got the Turnstile to **loop even on manual click** — classic deep-automation detection. Per Layer VI, the #1 CDP tell is the **`Runtime.enable` leak**. **Camoufox is Firefox/Juggler — it never speaks Chrome CDP**, so it sidesteps that vector entirely. That's *why* Camoufox passes CF+DataDome where patchright-Chrome can't. -> **Tier 2 = Camoufox (not a Chrome-CDP driver).** Note: this doc lists `rebrowser-playwright`/`patchright` as the Chrome-side fix; for FPS, Camoufox empirically outperformed it.

### KEYS WE STILL NEED TO ACCOUNT FOR
1. **JA4 + post-quantum (Layer 2/III) — VERIFY, don't assume.** Confirm our `curl_cffi` firefox135 ClientHello actually carries `X25519MLKEM768` (the 2026 binary tell) and a Firefox-matching JA4. We get 200, which implies yes, but verify against a JA4 echo (tls.peet.ws / scrapfly fp). Track Camoufox's real Firefox version and keep the `impersonate` target matched (firefox135 today).
2. **Header-order discipline (Layer 3).** `replay_cffi.py` currently injects `Accept`/`Accept-Language`/`Upgrade-Insecure-Requests` via a dict — risk of disrupting curl_cffi's browser-correct order. Let curl_cffi own defaults; append only cookies + `Referer`.
3. **`Accept-Language` <-> exit-IP geo (Layer 1/V).** Costless, high-impact — must match each IP's geography once we route through proxies.
4. **IP-binding x per-IP rate limit (Layer X).** `cf_clearance` is IP-locked AND FPS likely rate-limits per residential IP (3-5/IP at the strict end). So throughput scales as **N x (sticky IP + its own minted cookie set)** — NOT one cookie fanned across IPs. Plan the worker pool around (IP, cookie-jar) pairs.
5. **Re-challenge -> auto re-mint lifecycle.** Detect 403/`Cf-Mitigated`/DataDome captcha on a Tier-1 request -> invoke Tier-2 Camoufox mint -> refresh the IP-locked cookie jar -> resume. Track TTLs (`__cf_bm` ~30 min rotates; `cf_clearance` longer; `datadome` separate).
6. **Behavioral humanization on the Tier-2 mint (Layer VI).** Camoufox `humanize=True` covers cursor; add Bezier-ish paths, non-uniform delays, scroll micro-pauses, dwell-before-interaction to survive DataDome's behavioral layer during minting.
7. **New `/bot-check-submit` CF variant.** FPS now serves a landing interstitial with a checkbox AND a separate submit button; teach `handle_turnstile` to click the submit so minting stays hands-free.
8. **Cross-person reuse — UNTESTED, decides the economics.** Confirm one minted `cf_clearance` serves *many different* `/name/` URLs (should be domain-wide). If yes: one mint -> hundreds of scrapes (per Section VIII).
9. **Realistic ceiling (Layer X):** FPS ~= "CF Business+Turnstile + DataDome." Expect ~85-93% on the curl_cffi tier once cookies are live; budget for re-mints and per-IP caps. If FPS tightens to Enterprise+custom-WAF + hard per-IP limits, revisit economics.
10. **PACT (Section IX)** — monitor; future cryptographic-personhood threat, not actionable yet.
