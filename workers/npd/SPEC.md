# National Public Data (NPD) Scraper Specification

**Status**: Implemented (Route A — direct curl on serv01 :8789)

## Overview

Residential FastAPI service (same style as Zaba) scraping https://nationalpublicdata.com
people-search pages. **Not** Edge / universal-search (datacenter CF-blocks NPD).

## URL structure (confirmed)

```
https://nationalpublicdata.com/people/{last[0]}/{first}-{last}/
https://nationalpublicdata.com/people/{last[0]}/{first}-{last}/{state}/
https://nationalpublicdata.com/people/{last[0]}/{first}-{last}/{state}/{city}/
https://nationalpublicdata.com/people/{last[0]}/{first}-{last}/{state}/{city}/{id}/
```

Example: `/people/o/james-oehring/mo/cameron/pdww7krczz5jslv00ug5rdt7m0vhql24/`

## Phase 0 route decision (2026-08-07)

| Vantage | Method | Score | Notes |
|---------|--------|-------|-------|
| Laptop/DC | curl | 0/5 | CF 403/429 |
| Laptop/DC | urllib/httpx | 0/3 | blocked |
| serv01 | curl direct | **4/5** | person HTML |
| serv01 | httpx | 0/5 | TLS fingerprint |
| Flame+curl | curl --proxy | 0/5 | 403 |
| Browser | — | skipped | not needed |

**Chosen: A — Direct curl on serv01** (Flame-ready via `NPD_USE_FLAME=1`, currently off).

## Service

- Path on box: `C:\Users\scraper\npd-scraper`
- Port: **8789**
- `GET /health`
- `POST /v1/npd/search` `{ first_name, last_name, city?, state? }`
- Auth: `Bearer NPD_SERVICE_TOKEN`

## Field mapping (from Person JSON-LD)

| Field | Available | Source |
|-------|-----------|--------|
| name | yes | `Person.name` |
| age | yes | derived from `birthDate` year |
| aliases | no (not in free JSON-LD) | — |
| phones | yes | `telephone[]` |
| addresses | yes | `HomeLocation[].address` |
| relatives | yes | `relatedTo[]` |
| emails | yes | `email[]` |
| detail_link | yes | `Person.url` |
| social_media / employment / licenses / criminal | not on free card | — |

## Rate limiting / bot detection

- Cloudflare present; datacenter egress blocked.
- serv01 residential curl works; httpx often 403/429.
- Burst requests → intermittent 429 (retry/backoff in scraper).

## Implementation Checklist

- [x] Endpoint/URL structure confirmed
- [x] Response format and sample data (fixtures)
- [x] Field mapping documented
- [x] Auth: Bearer service token (no NPD site auth)
- [x] Rate limiting strategy (curl retry backoff)
- [x] Browser fingerprinting needed? **No**
- [x] Bot detection: CF on DC; residential curl OK
- [x] `npd_scraper.py` implementation
- [x] `test_npd.py` unit tests
- [ ] Integration test in `test-quickscan.sh` (optional later)
- [ ] **Do not** deploy live NPD to Supabase Edge

## Example

```python
from npd_scraper import search
import asyncio
print(asyncio.run(search("James", "Oehring", "Cameron", "MO")))
```

## Related

- Service: `workers/npd/service.py`
- Runner: `tests/scrape_runner.py --target npd`
- Template: `workers/zaba/`
