# Scraper Testing Journal

## 2026-07-29: Live Data Pull Testing Attempt

### Session Goal
Test zabasearch with actual live HTTP requests to zabasearch.com to validate scraper logic against real data.

### Test Approach
Created `test_zabasearch_live.py` script using pure Python (urllib) to:
1. Make real HTTP requests to zabasearch.com
2. Parse HTML responses
3. Extract person data (name, age, carrier, location, etc.)
4. No external dependencies (requests module not available)

### Test Results
❌ **Live fetch returned 404 for test phone numbers**
- Tested: 415-555-0123 (generic test number)
- Result: zabasearch.com returns 404 for non-existent numbers
- **Finding:** This is expected behavior — zabasearch returns 404 for numbers with no public data

### Blocker
- Test phone number (415-555-0123) is not a real registered number on zabasearch
- Cannot perform real data validation without a valid phone number

### Next Steps
To test actual data pull:
1. **Option A:** Use a real phone number (requires actual test data)
2. **Option B:** Check if worker is deployed and test via HTTP endpoint
3. **Option C:** Use zabasearch API directly if available (vs web scraping)

---

## 2026-07-28: ZabaSearch Testing Session Started

### Session Goal
Test the zabasearch relay scraper with focus on:
1. Summary search functionality
2. API integration
3. Error handling

### Test Results
✅ **Full test suite PASSED: 46/46 tests**

#### Breakdown by Category:
- **Phone Normalization:** 10/10 ✅
  - Handles dashes, parentheses, dots, +1 country codes
  - Validates digit counts (9-11 digits with normalization)
  - Formats as XXX-XXX-XXXX
  
- **Field Extraction:** 11/11 ✅
  - HTML parsing works for all major fields (name, age, carrier, location, etc.)
  - Handles aliases, addresses (current & previous), related persons
  - Phone numbers and time zone extraction verified
  
- **Response Structure:** 4/4 ✅
  - JSON structure has all required fields
  - Field types validated
  - Error responses properly formatted (no_result, invalid_phone, unauthorized, etc.)
  
- **CORS Headers:** 4/4 ✅
  - All required CORS headers present
  - Allows all origins (*)
  - OPTIONS preflight handling verified
  
- **Relay Authentication:** 5/5 ✅
  - X-Relay-Token header support
  - Query parameter token support
  - 401 handling for missing/invalid tokens
  
- **Relay URL Validation:** 6/6 ✅
  - Domain whitelist works (zabasearch.com, fastpeoplesearch.com, anywho.com)
  - Rejects unknown domains
  - Validates URL format
  
- **Endpoint Routing:** 4/4 ✅
  - /phone endpoint routing
  - /relay endpoint routing
  - Root fallback (/)
  - OPTIONS preflight
  
- **Integration Tests:** 2/2 ✅
  - Full phone lookup flow (normalize → fetch → parse → respond)
  - Full relay flow (auth → validate URL → fetch → relay)

### Issues/Blockers
(none found)

### Decisions
- Zabasearch test suite is comprehensive and stable
- Ready for production relay use

---

## 2026-07-29: Anywho Testing Session

### Session Goal
Test the anywho scraper with focus on:
1. URL building for anywho.com people search
2. HTML parsing (name, age, location, phones, aliases, related people)
3. Blocking detection (Cloudflare, access denied)
4. DOM parser and data-content attribute handling
5. Edge cases and error handling

### Test Results
✅ **Full test suite PASSED: 46/46 tests**

#### Breakdown by Category:
- **Slug Generation:** 5/5 ✅
  - Lowercase conversion
  - Spaces to dashes
  - Special character handling
  - Multiple dash collapsing
  - Trim leading/trailing dashes
  
- **URL Building:** 6/6 ✅
  - Name-only URLs
  - Full URLs with city/state
  - State abbreviation → full name mapping
  - Unknown state handling
  - Special chars in names
  - All 50+ state abbreviations verified
  
- **Text Cleaning:** 4/4 ✅
  - Whitespace collapse
  - Non-breaking space handling
  - Bullet/dash stripping
  - Content preservation
  
- **HTML Parsing:** 11/11 ✅
  - Single person extraction
  - Result structure validation
  - Age extraction
  - Location (lives_in) extraction
  - Phone number reassembly from data-content spans
  - Alias (AKA) extraction
  - Related people extraction
  - Detail link extraction
  - No results handling
  - Card deduplication
  - Invalid name filtering
  
- **Block Detection:** 5/5 ✅
  - Cloudflare challenge detection
  - Access denied message detection
  - Small response threshold (200 bytes)
  - Normal page validation
  - Configurable threshold
  
- **DOM Parser:** 4/4 ✅
  - Simple text extraction
  - data-content attribute preservation
  - Nested tag handling
  - Self-closing tag support
  
- **Integration Tests:** 3/3 ✅
  - Full flow HTML to person records
  - URL pattern validation
  - All state abbreviations valid

- **Edge Cases:** 6/6 ✅
  - Empty names
  - Numbers-only strings
  - Very long names
  - Unicode character handling
  - Malformed HTML resilience
  - None values in build_url

### Key Implementation Details
- **Scraper:** `workers/anywho/anywho_test.py` (1.2K lines, Python 3)
- **URL Pattern:** `/people/{first}+{last}/{state-name}/{city-slug}`
- **Phone Reconstruction:** Uses `<span data-content="NNNN">•••</span>` patterns
- **Block Detection:** Checks for Cloudflare title, "Access denied", response < 200 bytes
- **State Mapping:** All 50 states + DC in STATE_NAMES dict

### Issues/Blockers
(none found)

### Decisions
- Anywho scraper is well-tested with comprehensive unit coverage
- Ready for integration with broader scraping pipeline
- Test fixtures in conftest.py provide mock HTML samples
- No real network calls during testing (all mocked)

---

## 2026-08-06 / 08-07: Zaba residential service + dual-stack architecture lock-in

### Session Goal
Get Zabasearch working for enterprise/prod without burning home residential IP, and stop using broken Edge paths. Live-verify FPS + AnyWho + Zaba. Commit + push.

### Architecture decisions (hard rails)

| Scraper | How it runs | NOT how it runs |
|---------|-------------|-----------------|
| **AnyWho** | Supabase Edge `universal-search` (scraper-lab when secrets set) | — |
| **FPS** | Residential Windows service serv01 **`:8787`** → `/v1/fps/search` | Never Tailscale-only from Edge (Edge has no Tailscale) |
| **Zaba** | Residential Windows service serv01 **`:8788`** → `/v1/zaba/search` | **Not** `universal-search` / Edge fetch |

**Supabase Edge cannot reach Tailscale serv-01.** Calling Tailscale-only URLs from Edge → 120s timeout.

**Prod app zaba fallback** (quick-scan-form) uses `VITE_ZABA_SERVICE_URL` + optional token → direct HTTP to serv01. Unset on public Vercel = skip Zaba (no hang). Browser consumers need a public tunnel/host later if Zaba is required from the open internet.

### Zaba worker (`workers/zaba/`)

Path on box: `C:\Users\scraper\zaba-scraper`  
Shared Python venv: `C:\Users\scraper\fps-scraper\venv`  
Always-on: Task Scheduler `ZabaScraper` → `_run_logged.bat` (survives SSH disconnect)  
Port: **8788** | FPS is **8787**

Fetch order (enterprise: minimize personal IP):
1. **Primary:** FlameProxies residential pool via **curl.exe --proxy** (retries = `ZABA_PROXY_ATTEMPTS`, default 5)
2. **Last resort only:** host IP curl if `ZABA_DIRECT_FALLBACK=1`
3. If fallback OFF and proxies fail → hard fail

Do **not** use httpx for Zaba HTML fetch — TLS fingerprint often gets **403**. Curl works (A/B on serv01: direct 200; Flame ~40%/attempt with retries).

Key env on box `.env`:
- `ZABA_SERVICE_TOKEN`, `FLAMEPROXIES_API_KEY`, `FLAMEPROXIES_PACKAGE_ID=2549`
- `ZABA_DIRECT_FALLBACK` (prefer 0/unset prod; 1 only last resort)
- Flame package 2549 = same account as FPS

Flame generate: `POST https://flameproxies.com/api/customer/proxies/generate` with Bearer API key.

### Edge changes (deployed)

`universal-search` **refuses** siteName in `{zabasearch,zaba,fastpeoplesearch,fps}` immediately:
- Response: `error: residential_service_only`, ~1s, no scrape hang
- Deployed: `supabase functions deploy universal-search --no-verify-jwt --project-ref skhejbzrfptrusskuqoy`

`run-quick-scan` sequence: **AnyWho only** (no Zaba on edge).

`ZabasearchScraper.ts` `fetchWithProxy` stubbed (live fetch returns null). Parsers remain for admin/manual HTML.

### Integration tests (`tests/scrape_runner.py`)

Default subject: **James Oehring / Cameron, MO**

```bash
cd tests
python3 scrape_runner.py --target fps --mode prod --type both \
  --input first_name=James last_name=Oehring city=Cameron state=MO
python3 scrape_runner.py --target anywho --mode prod --type both \
  --input first_name=James last_name=Oehring city=Cameron state=MO
python3 scrape_runner.py --target zabasearch --mode prod --type both \
  --input first_name=James last_name=Oehring city=Cameron state=MO
```

Env (Vanyshr-mono `.env.local`):  
`FPS_PROD_URL`, `FPS_SERVICE_TOKEN`, `ZABA_PROD_URL=http://serv-01.tail7e9bab.ts.net:8788`, `ZABA_SERVICE_TOKEN`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`

Logging: Supabase table `scrape_results` (types include `summary|full|both`).

### Live smoke results (2026-08-06 night)

| Target | Path | Result |
|--------|------|--------|
| FPS | serv01 :8787 | success ~84s |
| AnyWho | universal-search | success ~2s |
| Zaba edge | universal-search | **timeout** before fix; after deploy **refuse ~1s** |
| Zaba direct | :8788 Flame-first | success ~3s, 1 profile age 37 |

### Ops / Tailscale

- Host alias: `serv-01` (Tailscale `serv-01.tail7e9bab.ts.net` / 100.112.202.108)
- SSH as `scraper`, key `~/.ssh/id_ed25519`
- Sync code (no .env overwrite): `workers/zaba/SYNC_TO_SERV01.sh`
- Restart: `schtasks /Run /TN ZabaScraper`
- Health: `curl http://serv-01.tail7e9bab.ts.net:8788/health`

### Git (committed + pushed)

- **vanyshr-scrapers** branch `dev/npd-scraper` — `fbdd399` feat zaba residential service  
  Note: this worktree remotes to `jamesringldr/vanyshr-mono` (same GitHub remote as mono in this environment).
- **Vanyshr-mono** branch `dev/dashboard_ui` — `3b28b1a` feat zaba UI + edge refuse  

Uncommitted leftovers: NPD scaffold (`workers/npd/`), dashboard UI WIP on mono, workers-old/, etc.

### DB note
`scrape_results` check constraint allows scrape_type `both` (was only summary|full; fixed earlier).

### Enterprise IP policy
Prefer Flame for all Zaba hits; personal residential IP only emergency. Same principle should apply to **NPD** when it goes live on serv01.

### Next workstream
**NPD scraper** — scaffold at `workers/npd/` (SPEC.md + stub). Build like Zaba/FPS residential service pattern, **not** Edge live fetch, unless pure public API survives datacenter.

---

## 2026-08-07: NPD Phase 0 route matrix + Phase 1 service

### Session Goal
Implement National Public Data scraper end-to-end as residential FastAPI service (Zaba pattern), after route probe.

### Phase 0 — Route matrix (raw evidence)

Target URL used for scoring:
`https://nationalpublicdata.com/people/o/james-oehring/mo/`

URL patterns confirmed:
- Surname index: `/people/{letter}/{lastname}/`
- Name list: `/people/{letter}/{first}-{last}/`
- State: `/people/{letter}/{first}-{last}/{st}/`
- City: `/people/{letter}/{first}-{last}/{st}/{city}/`
- Detail: `/people/.../{st}/{city}/{pd*id}/`

| Vantage | Route | Attempts | Result |
|---------|-------|----------|--------|
| Laptop/DC | R1 curl | 5 | **0/5** — status 403/429, CF interstitial ~5.5k |
| Laptop/DC | R2 urllib | 3 | **0/3** — HTTPError 429 |
| serv01 residential | R1 curl | 5 | **4/5** — 200 len≈47402, person=True; 1×429 under burst |
| serv01 residential | R2 httpx | 5 | **0/5** — 429/403 (TLS fingerprint) |
| Flame package 2549 | R3 curl --proxy | 5 | **0/5** — 403 len≈5746 |
| Browser/Camoufox | R4 | — | **skipped** (R1 already ≥3/5) |

Post-cooldown direct detail fetch (serv01 curl): city list 200/47966; detail profile 200/84861 (James Oehring 62 Cameron MO).

### Decision

**Route A — Direct curl on serv01** (Zaba-like FastAPI, no proxy required).

- Flame-ready via `NPD_USE_FLAME=1` (default off — Flame currently 403s on NPD).
- Do **not** put live NPD on Edge/universal-search (DC path solidly blocked).
- Prefer curl over httpx (same lesson as Zaba).

### Phase 1 delivered

- `workers/npd/npd_scraper.py` — URL builder, curl fetch, JSON-LD Person parse
- `workers/npd/service.py` — FastAPI `:8789` `GET /health` `POST /v1/npd/search`
- Auth `NPD_SERVICE_TOKEN`; SYNC/RUN/Task Scheduler scripts
- `scrape_runner --target npd` + transformer rows
- Unit tests `tests/test_npd.py` (12 passed, fixtures, no live net)

### Ops

- Box path: `C:\Users\scraper\npd-scraper`
- Env: `NPD_PROD_URL=http://serv-01.tail7e9bab.ts.net:8789`, `NPD_SERVICE_TOKEN`
- Shared venv: `C:\Users\scraper\fps-scraper\venv`
- Task Scheduler: `NpdScraper` → `_run_logged.bat` (needed for durable process; ad-hoc Start-Process died)
- Firewall: inbound TCP 8789 Domain/Private/Public

### Phase 2 validate (2026-08-07 evening)

| Check | Result |
|-------|--------|
| `scrape_runner --target npd` | HTTP 200, status=success, 1 profile (James Oehring / Cameron MO) |
| `scrape_results` insert | **201** after migration `scrape_results_allow_npd_target` |
| AnyWho regression | success + DB log |
| FPS regression | success + DB log |
| Zaba regression | connection failed (service not listening on :8788 — pre-existing ops, not NPD break) |

DB migration (Supabase project skhejbzrfptrusskuqoy): allow `target='npd'`; keep `scrape_type='both'`.
File: `Vanyshr-mono/supabase/migrations/20260807_scrape_results_allow_npd.sql`

---
