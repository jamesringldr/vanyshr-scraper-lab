# Zaba (ZabaSearch) Scraper Testing Journal

**Target**: Zaba (search.zaba.com)
**Type**: Residential data broker with IP-based blocking
**Pages**: Full Profile Only (Multiple Results On Single Page)
**Status**: ✅ Code ready, requires residential IP access (not context.dev Extract)

## Overview
Zaba displays all search results on a single page with full profile information for each result. No separate summary page - results ARE full profiles.

**CRITICAL FINDING (2026-08-11)**: Zaba blocks datacenter/API access (including context.dev). Requires residential IP as per existing serv01:8788 service.

## Implementation Status

### ✅ Completed
- [x] Scraper module built (structure for multi-profile extraction)
- [x] URL building: `/s?q=[FirstName]+[LastName]&where=[City],+[State]`
- [x] Schema definition for multiple profile extraction
- [x] Profile data extraction and model mapping
- [x] Error handling and logging
- [x] Unit tests: 5/5 passing

### ❌ Context.dev Extract NOT VIABLE
- Zaba blocks context.dev (WEBSITE_ACCESS_ERROR: 400)
- Blocks all datacenter/API access
- Requires **residential IP** for access

### ✅ Existing Solution
- Zaba already accessible via **serv01:8788** (residential Windows service)
- Uses **curl + Flame proxies** (from journal notes 2026-08-06/07)
- Rate limiting: max 1 FPS request per 30 seconds

## Unit Test Results (2026-08-11)

### Test Coverage: 5/5 Passing ✅

1. **Scraper Parameters** — Parameter validation
2. **URL Building** — Correct Zaba query format
3. **Age Parsing** — Number extraction from strings
4. **Multiple Profile Extraction** — Handle multiple results
5. **Empty Data Handling** — Graceful fallback

## Live Testing Result: BLOCKED

**Finding**: Context.dev Extract cannot access Zaba
```
Error code: 400 - 'No Markdown content could be extracted'
Message: WEBSITE_ACCESS_ERROR
```

Zaba has strong anti-scraping measures that:
- Block all datacenter IPs
- Block all API/proxy access
- Require residential IP for access

## Why Zaba Works on serv01:8788

According to journal (2026-08-06/07):
- **Primary**: FlameProxies residential pool (Flame package 2549)
- **Fallback**: Host IP curl (if `ZABA_DIRECT_FALLBACK=1`)
- **Port**: 8788 (Windows Task Scheduler service)
- **Key env vars**: `ZABA_SERVICE_TOKEN`, `FLAMEPROXIES_API_KEY`
- **Method**: curl only (httpx gets 403s - TLS fingerprint issue)

Zaba achieves success via residential IP + proper TLS fingerprint, not via APIs.

## Recommendation

**Do NOT use context.dev Extract for Zaba**. 

For Zaba scraping:
1. **Option A** (RECOMMENDED): Use existing serv01:8788 service
   - Already deployed and tested (2026-08-06 live smoke test PASSED)
   - Proven to work with curl + Flame proxies
   - Rate-limited to 1 req/30s across all concurrent jobs
   - Cost: ~$0.20/request (Flame proxy pool)

2. **Option B**: Separate residential machine/IP
   - Same pattern as serv01 implementation
   - Higher setup/maintenance cost
   - Parallel redundancy benefit

3. **Option C** (NOT VIABLE): Context.dev Extract
   - Blocked by Zaba
   - No workaround for residential IP requirement

## Code Status

The `ZabaScraper` class is built correctly for:
- Multi-profile extraction (all results on one page)
- Proper data model mapping
- Error handling and logging
- Cache optimization

**BUT**: Cannot be used with context.dev Extract due to IP blocking.

This scraper code WOULD work if:
- Zaba allowed API access (they don't)
- context.dev supported residential proxy pass-through (it doesn't expose this option)

## Related: serv01 Integration

Zaba is already productionized via `workers/zaba/` → serv01:8788
- Live smoke test: PASSED (2026-08-06)
- Payload latency: ~3s
- Service health: Active (Task Scheduler `ZabaScraper`)

For app integration, use existing `VITE_ZABA_SERVICE_URL` endpoint.

## Technical Details

**URL Pattern**: `/s?q={FirstName}+{LastName}&where={City},+{state}`
- Example: `https://search.zaba.com/s?q=James+Oehring&where=Cameron,+mo`
- Results: All full profiles rendered on single page
- Each profile: name, age, address, phone, relatives, properties

**Data Extraction Challenge**: 
- Context.dev extracts from Markdown/HTML content
- Zaba requires residential IP to serve content
- No residential proxy option in context.dev Extract API

## Conclusion

Zaba scraping requires residential IP access that context.dev Extract API cannot provide. The modular scraper code (`ZabaScraper`) is production-ready for a hypothetical environment where Zaba allowed API access, but in reality, Zaba must be accessed via:
- **Option A**: Existing serv01:8788 residential service (recommended)
- **Option B**: Alternative residential infrastructure

This finding reinforces the hybrid scraping strategy: use context.dev for API-accessible data brokers (FPS, NPD), use residential services for IP-blocked brokers (Zaba).