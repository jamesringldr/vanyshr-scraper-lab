# Scraper Testing Punchlist

## Working (production path)

### AnyWho
- [x] Unit suite
- [x] Live via universal-search / scrape_runner

### FPS
- [x] Residential service serv01 :8787
- [x] Live scrape_runner prod smoke

### Zaba
- [x] Flame-first curl service workers/zaba :8788
- [x] Edge refuse residential (deployed)
- [x] scrape_runner direct to serv01
- [x] App quick-scan uses VITE_ZABA_SERVICE_URL (not edge)
- [ ] Public hostname/tunnel for browser users outside Tailscale
- [ ] Rotate ZABA_SERVICE_TOKEN after paste history

### NPD
- [x] Route probe: DC blocked; serv01 curl 4/5; httpx 0/5; Flame 0/5 → **Route A direct curl**
- [x] workers/npd FastAPI service (:8789)
- [x] scrape_runner --target npd
- [x] Field map via Person JSON-LD → scrape_results transformer
- [x] Do **not** put live NPD behind Edge (DC CF-blocked)
- [x] Live smoke on serv01 + scrape_results (constraint allows `npd`)
- [x] Task Scheduler `NpdScraper` + firewall rule port 8789
- [ ] Re-probe Flame later (`NPD_USE_FLAME=1`) if residential pool improves
- [ ] App config `VITE_NPD_SERVICE_URL` (optional, later — mirror Zaba)

## Issues
### Open
- Zaba/FPS/NPD not reachable from public Vercel without tunnel
- Edge phone-lookup still imports ZabasearchScraper (legacy; separate cleanup)
- NPD uses host residential IP (Flame blocked on this target) — watch rate limits / IP burn

### Closed 2026-08-07
- Zaba edge 120s timeout (blocked edge route; residential service is source of truth)
- Personal IP burn on Zaba: Flame-first; ZABA_DIRECT_FALLBACK last resort only
- NPD route choice: direct curl on serv01 (not Edge, not browser)
