# VPS scraper stack runbook

**Home residential pilot:** see [HOME_WORKER.md](HOME_WORKER.md) — worker on your Mac, API + Redis on VPS.

## Prerequisites

- DNS: `scraper-lab.vanyshr.com` → VPS IP (grey cloud for LE).
- Repo at `/opt/vanyshr/scraper-lab`.
- `config/env/.env` created from `config/env/.env.local.example`.

## Deploy / update

```bash
cd /opt/vanyshr/scraper-lab
# edit config/env/.env — set SCRAPER_TOKEN
docker compose build
docker compose up -d
docker compose ps
```

## Caddy (reverse proxy to API)

```bash
cd /opt/vanyshr/scraper-lab/deploy/caddy
docker compose up -d
```

## Smoke test

```bash
curl -sS https://scraper-lab.vanyshr.com/health

export SCRAPER_TOKEN='your-token'
curl -sS -X POST https://scraper-lab.vanyshr.com/v1/quickscan/search \
  -H "Authorization: Bearer $SCRAPER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"James","last_name":"Oehring","city":"Cameron","state":"MO"}'

# Poll job (replace JOB_ID):
curl -sS -H "Authorization: Bearer $SCRAPER_TOKEN" \
  https://scraper-lab.vanyshr.com/v1/jobs/JOB_ID
```
