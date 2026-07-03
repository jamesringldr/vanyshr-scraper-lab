# Scraper-Lab Duct-Tape Bridge

How prod Vanyshr QuickScan reaches a **residential-IP Mac mini worker** via the `scraper-lab` API (VPS) during the pilot, without rewriting the prod UI or merging repos.

- **API host:** `https://scraper-lab.vanyshr.com` (VPS `178.156.171.112`)
- **Queue:** Redis on the VPS (`127.0.0.1:6379`, bound locally)
- **Worker:** Mac mini at home, consuming `scraper:jobs` over an SSH tunnel
- **Edge bridge:** `supabase/functions/_shared/scraper-lab-client.ts` invoked from `supabase/functions/universal-search/index.ts` when `SCRAPER_LAB_URL` + `SCRAPER_LAB_TOKEN` are set.
- **Pilot plan (source of truth):** `vanyshr-scraper-lab/deploy/vps-duct-tape-plan.md`
- **Home worker setup:** `vanyshr-scraper-lab/deploy/HOME_WORKER.md`

## How it routes

1. UI calls `universal-search` with `siteName: "AnyWho" | "Zabasearch"` (one source per call — never `search_all` from prod for the pilot).
2. If `scraperLabEnabled()` is true, the bridge posts to `POST /v1/quickscan/search` with `sources: ["anywho"]` or `["zabasearch"]` only.
3. VPS API enqueues the job in Redis. Mac mini worker pops it and scrapes from the residential IP.
4. Edge polls `GET /v1/jobs/:id` until `completed` or `failed` (max `SCRAPER_LAB_POLL_MAX_SEC`).
5. `quick_scans` row is updated: `scanning` → `selection_required` | `no_matches` | `scraper_failed`.

If `SCRAPER_LAB_URL` or `SCRAPER_LAB_TOKEN` is unset, `universal-search` falls back to the original datacenter in-process scrapers — no behavior change for local dev.

## Required Supabase secrets

| Variable | Value |
|----------|-------|
| `SCRAPER_LAB_URL` | `https://scraper-lab.vanyshr.com` |
| `SCRAPER_LAB_TOKEN` | The `SCRAPER_TOKEN` from VPS `/opt/vanyshr/scraper-lab/config/env/.env` |
| `SCRAPER_LAB_POLL_MAX_SEC` | `150` |
| `SCRAPER_LAB_POLL_MS` | `2000` |

The token MUST be identical to the VPS `SCRAPER_TOKEN` and the Mac mini `.env.home` `SCRAPER_TOKEN`.

## Ops

### VPS — keep API + Redis up, stop datacenter worker

Only one consumer may drain `scraper:jobs`. During the pilot the Mac mini owns it.

```bash
ssh deploy@178.156.171.112
cd /opt/vanyshr/scraper-lab
git pull
docker compose pull
docker compose up -d redis scraper-api
docker compose --profile datacenter stop scraper-worker 2>/dev/null || true
curl -sS https://scraper-lab.vanyshr.com/health
# Expected: {"status":"ok","redis":"ok"}
```

### Mac mini — tunnel + worker (two terminals)

Migration from the prior MacBook: copy `config/env/.env.home` over, then refresh the Chrome path:

```bash
mdfind -name 'Google Chrome for Testing'
# Paste the full .../Contents/MacOS/Google Chrome for Testing path into
# CHROME_FOR_TESTING_BIN in config/env/.env.home (quote if it contains spaces).
```

Terminal A — Redis tunnel (keep open):

```bash
cd /path/to/vanyshr-scraper-lab
./scripts/home-redis-tunnel.sh
```

Terminal B — worker (keep open):

```bash
cd /path/to/vanyshr-scraper-lab
./scripts/run-home-worker.sh
# Expected: scraper-worker started (egress=home)
```

Smoke test (anywho-only contract used by the prod first screen):

```bash
cd /path/to/vanyshr-scraper-lab
./scripts/verify-duct-tape.sh
# Or the broader: ./scripts/test-quickscan.sh James Oehring Cameron MO
```

System hygiene: disable sleep (`caffeinate -dimsu` or System Settings), wired Ethernet, autossh per `HOME_WORKER.md` if you want auto-recovery.

### Supabase — enable the bridge

```bash
cd /path/to/vanyshr-mono
supabase link   # if not already
supabase secrets set \
  SCRAPER_LAB_URL="https://scraper-lab.vanyshr.com" \
  SCRAPER_LAB_TOKEN="PASTE_FROM_VPS_SCRAPER_TOKEN" \
  SCRAPER_LAB_POLL_MAX_SEC="150" \
  SCRAPER_LAB_POLL_MS="2000"
supabase functions deploy universal-search
```

Verify:

```bash
supabase secrets list
# Then exercise the edge:
supabase functions invoke universal-search --body '{
  "firstName": "James",
  "lastName": "Oehring",
  "city": "Cameron",
  "state": "MO",
  "siteName": "AnyWho"
}'
```

Look for `🏠 Using scraper-lab` and `🏠 scraper-lab job ... completed` in Supabase Functions logs.

## Env matrix

| Variable | Where set | Source |
|----------|-----------|--------|
| `SCRAPER_TOKEN` | VPS `config/env/.env`, Mac `config/env/.env.home`, Supabase `SCRAPER_LAB_TOKEN` | Same string everywhere |
| `SCRAPER_LAB_URL` | Supabase secret | `https://scraper-lab.vanyshr.com` |
| `SCRAPER_LAB_POLL_MAX_SEC` | Supabase secret | `150` |
| `SCRAPER_LAB_POLL_MS` | Supabase secret | `2000` |
| `CHROME_FOR_TESTING_BIN` | Mac `config/env/.env.home` | `mdfind -name 'Google Chrome for Testing'` |
| `REDIS_URL` | Mac `config/env/.env.home` | `redis://127.0.0.1:6379` (via tunnel) |
| `SCRAPER_EGRESS` | Mac `config/env/.env.home` | `home` |

## Rollback (instant)

```bash
cd /path/to/vanyshr-mono
supabase secrets unset SCRAPER_LAB_URL SCRAPER_LAB_TOKEN
supabase functions deploy universal-search
```

Prod returns to datacenter edge scrapers. No further changes required.

## GO / NO-GO checklist (demo day)

- [ ] `curl https://scraper-lab.vanyshr.com/health` → `{"status":"ok","redis":"ok"}`
- [ ] VPS `scraper-worker` (datacenter profile) **stopped**
- [ ] Mac mini tunnel up (Terminal A)
- [ ] Mac mini worker up — log shows `scraper-worker started (egress=home)`
- [ ] `./scripts/verify-duct-tape.sh` passed in the last 30 min
- [ ] Supabase secrets `SCRAPER_LAB_*` set
- [ ] `universal-search` deployed after secret change
- [ ] Supabase Functions logs show `🏠 Using scraper-lab` on a test invoke
- [ ] Prod UI QuickScan tested end-to-end for the golden persona
- [ ] Rollback command rehearsed
