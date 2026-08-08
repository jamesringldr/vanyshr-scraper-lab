# Vanyshr Scraper Quick Recall

Updated: 2026-08-07 (NPD Route A live on :8789)

## Dual-stack rule (important)

| Runtime | Scrapers |
|---------|----------|
| **Supabase Edge** (`universal-search`) | AnyWho only (live). FPS/Zaba names **refused** (`residential_service_only`). |
| **Residential serv01** (Tailscale) | FPS `:8787`, Zaba `:8788`, NPD `:8789` — Bearer token auth |

Edge has **no** Tailscale. Never put serv-01 URLs in Edge secrets expecting live scrape.

## Working scrapers

### AnyWho
- Edge via `universal-search` / scraper-lab
- Worker parse reference: `workers/anywho/anywho_test.py`
- Tests: `tests/test_anywho.py`

### FPS (FastPeopleSearch)
- Service: `workers/fps-playwright/service.py` on serv01 `:8787`
- `POST /v1/fps/search` `{ first_name, last_name, city?, state? }`
- Env: `FPS_PROD_URL`, `FPS_SERVICE_TOKEN`
- Camoufox / browser stack (long runs ~60–90s)

### Zaba
- Service: `workers/zaba/` on serv01 `C:\Users\scraper\zaba-scraper` `:8788`
- `POST /v1/zaba/search` `{ first_name, last_name, city?, state? }`
- Fetch: FlameProxies via **curl --proxy** first; optional `ZABA_DIRECT_FALLBACK=1` last resort only
- Env: `ZABA_PROD_URL`, `ZABA_SERVICE_TOKEN`, `FLAMEPROXIES_API_KEY`, package **2549**
- Task Scheduler: `ZabaScraper`
- App fallback: `VITE_ZABA_SERVICE_URL` (not edge)

### NPD
- Service: `workers/npd/` on serv01 `:8789` — `POST /v1/npd/search`
- Fetch: **direct curl** (Phase 0 Route A); `NPD_USE_FLAME=1` optional (Flame was 0/5)
- Env: `NPD_PROD_URL`, `NPD_SERVICE_TOKEN`, optional `FLAMEPROXIES_*`
- Do **not** Edge-live; DC CF-blocks nationalpublicdata.com

## Integration runner

```bash
cd vanyshr-scrapers/tests
python3 scrape_runner.py --target <fps|anywho|zabasearch|npd> --mode prod --type both \
  --input first_name=James last_name=Oehring city=Cameron state=MO
```

Logs → Supabase `scrape_results` (types: summary|full|both).

## Default smoke person
James Oehring, Cameron, MO

## Journal
See `context/journal.md` for session history.
