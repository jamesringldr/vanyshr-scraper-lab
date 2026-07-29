# Scrape Runner — Integration Test Tool

Execute actual scrapers (fps, anywho, zabasearch) and log results to the `scrape_results` database table for analysis and debugging.

## Overview

**scrape_runner.py** is a CLI tool that:
- Runs scrapers in **local** (this machine) or **prod** (serv01 via FlameProxies) mode
- Retrieves **summary** and/or **full profile** results
- Transforms results to standardized DB schema
- Logs each result as a separate row with consistent scrape_id
- Supports **QuickScan** mode for optimized multi-scraper execution

---

## Installation

### Prerequisites
```bash
# Install dependencies (if not already in venv)
pip install httpx python-dotenv
```

### Environment Setup
Create or update `.env.local` in Vanyshr-mono root:

```bash
# Supabase credentials
SUPABASE_URL=https://skhejbzrfptrusskuqoy.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>

# Scraper endpoints (local mode)
FPS_LOCAL_ENDPOINT=http://localhost:3000/fps
ANYWHO_LOCAL_ENDPOINT=http://localhost:3001/anywho
ZABASEARCH_LOCAL_ENDPOINT=http://localhost:3002/relay

# Scraper endpoints (prod mode)
FPS_PROD_ENDPOINT=http://serv01:3000/fps
ANYWHO_PROD_ENDPOINT=http://serv01:3001/anywho
ZABASEARCH_PROD_ENDPOINT=http://serv01:3002/relay

# QuickScan sequence (comma-separated, default: fps,anywho,zabasearch)
QUICKSCAN_MODE=fps,anywho,zabasearch
```

---

## Usage

### Basic Syntax
```bash
python scrape_runner.py --target TARGET --mode MODE --type TYPE [--input KEY=VALUE ...]
```

### Arguments

| Argument | Values | Description |
|----------|--------|-------------|
| `--target` | `fps`, `anywho`, `zabasearch`, `quickscan` | Scraper(s) to run |
| `--mode` | `local`, `prod` | Execution mode |
| `--type` | `summary`, `full`, `both` | Result type(s) |
| `--input` | `key=value ...` | Input data (space-separated) |
| `--scrape-id` | STRING | Override auto-generated scrape_id |
| `--db-url` | URL | Supabase URL (default: from .env) |
| `--db-key` | STRING | Supabase key (default: from .env) |
| `--verbose` | FLAG | Enable debug logging |
| `--no-log` | FLAG | Skip DB logging (debug mode) |

### Examples

#### 1. FPS — Summary, Local
```bash
python scrape_runner.py \
  --target fps \
  --mode local \
  --type summary \
  --input first_name=John last_name=Doe city="San Francisco" state=CA
```

Output:
```json
[
  {
    "scrape_id": "fps.07.29.14.22",
    "target": "fps",
    "mode": "local",
    "scrape_type": "summary",
    "input_data": {...},
    "results": [...],
    "status": "success",
    "response_time_ms": 2345,
    "response_bytes": 4250,
    "errors": null
  }
]
```

#### 2. Anywho — Full Profile, Prod
```bash
python scrape_runner.py \
  --target anywho \
  --mode prod \
  --type full \
  --input first_name=Jane last_name=Smith city="Los Angeles" state=CA
```

#### 3. Zabasearch — Summary, Local (Phone Lookup)
```bash
python scrape_runner.py \
  --target zabasearch \
  --mode local \
  --type summary \
  --input phone="415-555-0123"
```

#### 4. QuickScan — Both Modes, Local
Runs all three scrapers in sequence (fps → anywho → zabasearch):

```bash
python scrape_runner.py \
  --target quickscan \
  --mode local \
  --type both \
  --input first_name=John last_name=Doe city="San Francisco" state=CA
```

Output: Array of 3 result sets (one per scraper)

#### 5. Skip DB Logging (Debug Mode)
```bash
python scrape_runner.py \
  --target fps \
  --mode local \
  --type summary \
  --input first_name=John last_name=Doe \
  --no-log
```

#### 6. Verbose Output
```bash
python scrape_runner.py \
  --target anywho \
  --mode local \
  --type summary \
  --input first_name=John last_name=Doe \
  --verbose
```

---

## Input Data Format

Input is passed as space-separated `key=value` pairs. Quotes are optional but recommended for multi-word values.

### FPS Input
- `first_name` — First name (required for name search)
- `last_name` — Last name (required for name search)
- `city` — City (optional)
- `state` — State abbreviation (optional)

### Anywho Input
- `first_name` — First name (required)
- `last_name` — Last name (required)
- `city` — City (optional)
- `state` — State abbreviation (optional)

### Zabasearch Input
- `phone` — Phone number (required, any format: 4155550123, 415-555-0123, etc.)

---

## Database Schema

Results are stored in `scrape_results` table:

| Column | Type | Notes |
|--------|------|-------|
| id | BIGSERIAL | Auto-increment PK |
| scrape_id | TEXT | target.MM.DD.HH.MM (e.g., fps.07.29.14.22) |
| target | TEXT | fps \| anywho \| zabasearch |
| mode | TEXT | local \| prod |
| scrape_type | TEXT | summary \| full |
| input_data | JSONB | Original input {name, city, state, phone, etc.} |
| summary_results | JSONB | {name, age, location, phones, ...} |
| full_profile_results | JSONB | {carrier, birth_year, timezone, addresses, ...} |
| errors | TEXT | Error message if status != success |
| status | TEXT | success \| partial \| failed \| timeout \| blocked |
| response_time_ms | INTEGER | Scrape duration |
| response_bytes | INTEGER | Response size |
| created_at | TIMESTAMPTZ | Timestamp |
| updated_at | TIMESTAMPTZ | Updated timestamp |

### Scrape ID Format
Format: `{target}.{MM}.{DD}.{HH}.{MM}`
- `MM` — 2-digit month (01-12)
- `DD` — 2-digit day (01-31)
- `HH` — 2-digit hour (00-23)
- `MM` — 2-digit minute (00-59)

Examples:
- `fps.07.29.14.22` — FPS scrape on July 29 at 2:22 PM
- `anywho.07.29.23.59` — Anywho scrape on July 29 at 11:59 PM

### Status Codes

| Status | Meaning | Notes |
|--------|---------|-------|
| `success` | Scraped successfully | Results populated |
| `partial` | Partial results | Some fields missing |
| `failed` | Scraper error | Check `errors` column |
| `timeout` | Request timeout | Exceeded 60s |
| `blocked` | Blocked by WAF/CAPTCHA | Cloudflare, reCAPTCHA, or small response |

---

## Result Structure Examples

### FPS Summary Result
```json
{
  "scrape_id": "fps.07.29.14.22",
  "target": "fps",
  "mode": "local",
  "scrape_type": "summary",
  "input_data": {"first_name": "John", "last_name": "Doe", "city": "San Francisco", "state": "CA"},
  "results": [
    {
      "name": "John Doe",
      "age": "42",
      "location": "San Francisco, CA",
      "phones": ["415-555-0123"],
      "detail_link": "https://www.fastpeoplesearch.com/name/john-doe"
    }
  ],
  "status": "success",
  "response_time_ms": 2345,
  "response_bytes": 4250,
  "errors": null
}
```

### Anywho Summary Result (Multiple Results)
```json
{
  "scrape_id": "anywho.07.29.15.10",
  "target": "anywho",
  "mode": "local",
  "scrape_type": "summary",
  "input_data": {"first_name": "John", "last_name": "Doe"},
  "results": [
    {"name": "John Doe", "age": "42", "location": "San Francisco, CA", "phones": ["415-555-0123"], "aka": "Johnny Doe", "related": "Jane Doe", "detail_link": "https://..."},
    {"name": "John Doe", "age": "38", "location": "Oakland, CA", "phones": ["510-555-9999"], "aka": null, "related": null, "detail_link": "https://..."}
  ],
  "status": "success",
  "response_time_ms": 3456,
  "response_bytes": 8900,
  "errors": null
}
```

Each result in the `results` array will be logged as a separate row in the DB, all sharing the same `scrape_id`.

### Zabasearch Full Profile Result
```json
{
  "scrape_id": "zabasearch.07.29.16.30",
  "target": "zabasearch",
  "mode": "local",
  "scrape_type": "full",
  "input_data": {"phone": "415-555-0123"},
  "results": [
    {
      "name": "John Doe",
      "age": "42",
      "birth_year": "1982",
      "line_type": "Landline",
      "carrier": "AT&T",
      "location": "San Francisco, CA",
      "time_zone": "Pacific",
      "phones": ["415-555-0123"],
      "aliases": ["Johnny Doe", "J.D."],
      "most_recent_address": "123 Main St, San Francisco, CA 94102",
      "previous_addresses": ["456 Oak Ave, Oakland, CA 94601"],
      "email_domains": ["@example.com"],
      "previous_phones": ["415-555-0124"],
      "social_media": [],
      "jobs": [],
      "education": [],
      "professional_licenses": [],
      "related_persons": [{"name": "Jane Doe", "href": "/person/jane-doe"}]
    }
  ],
  "status": "success",
  "response_time_ms": 1234,
  "response_bytes": 8456,
  "errors": null
}
```

### Blocked Result (Cloudflare Challenge)
```json
{
  "scrape_id": "fps.07.29.17.00",
  "target": "fps",
  "mode": "prod",
  "scrape_type": "summary",
  "input_data": {"first_name": "Jane", "last_name": "Smith", "city": "Los Angeles", "state": "CA"},
  "results": [],
  "status": "blocked",
  "response_time_ms": 5000,
  "response_bytes": 402,
  "errors": "Cloudflare Turnstile challenge detected, unable to proceed"
}
```

---

## Querying Results

### Find All Scrapes for a Target
```sql
SELECT * FROM scrape_results 
WHERE target = 'fps' 
ORDER BY created_at DESC
LIMIT 10;
```

### Find All Results from One Scrape Run
```sql
SELECT * FROM scrape_results 
WHERE scrape_id = 'fps.07.29.14.22' 
ORDER BY created_at;
```

### Find Blocked/Failed Scrapes
```sql
SELECT * FROM scrape_results 
WHERE status IN ('blocked', 'failed') 
ORDER BY created_at DESC
LIMIT 20;
```

### Success Rate by Target (Last 7 Days)
```sql
SELECT 
    target,
    COUNT(*) FILTER (WHERE status = 'success') AS successful,
    COUNT(*) FILTER (WHERE status != 'success') AS failed,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'success') / COUNT(*), 2) AS success_rate
FROM scrape_results
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY target;
```

### Average Response Time by Scraper
```sql
SELECT 
    target,
    ROUND(AVG(response_time_ms), 0) AS avg_ms,
    MIN(response_time_ms) AS min_ms,
    MAX(response_time_ms) AS max_ms,
    COUNT(*) AS runs
FROM scrape_results
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY target
ORDER BY avg_ms DESC;
```

---

## Troubleshooting

### "SUPABASE_URL or SUPABASE_ANON_KEY not set"
**Solution**: Set environment variables in `.env.local` or pass via CLI:
```bash
python scrape_runner.py \
  --target fps \
  --mode local \
  --type summary \
  --input first_name=John last_name=Doe \
  --db-url https://your-project.supabase.co \
  --db-key your-anon-key
```

### "Connection refused" (local mode)
**Solution**: Ensure scraper workers are running on localhost:
- FPS: `http://localhost:3000/fps`
- Anywho: `http://localhost:3001/anywho`
- Zabasearch: `http://localhost:3002/relay`

### "Timeout after 60s"
**Solution**: Scraper took too long. Check:
- Network connectivity
- Scraper worker status
- Blocking/WAF issues (try `--mode prod`)

### "status: blocked"
**Solution**: Scraper detected blocking (Cloudflare, reCAPTCHA, or small response):
- For local mode: Ensure Camoufox fingerprinting is working
- For prod mode: Verify FlameProxies are active on serv01
- Check `errors` column in DB for details

### "No results to log (status: failed)"
**Solution**: Scraper encountered an error. Check:
- Input data format (required fields present?)
- Scraper endpoint reachable?
- Check logs for detailed error message (use `--verbose`)

---

## Advanced Usage

### Custom Scrape ID
Override the auto-generated scrape_id for special scenarios:
```bash
python scrape_runner.py \
  --target fps \
  --mode local \
  --type summary \
  --input first_name=John last_name=Doe \
  --scrape-id fps.custom.test.001
```

### Batch Scraping (Shell Script)
```bash
#!/bin/bash
# Scrape multiple people
people=(
  "John Doe San Francisco CA"
  "Jane Smith Los Angeles CA"
  "Jack Brown Denver CO"
)

for person in "${people[@]}"; do
  read fname lname city state <<< "$person"
  python scrape_runner.py \
    --target fps \
    --mode local \
    --type summary \
    --input first_name="$fname" last_name="$lname" city="$city" state="$state"
  sleep 2  # Rate limiting
done
```

### Monitor Scraping in Real-Time
```bash
# In terminal 1: Run scrape runner
python scrape_runner.py \
  --target quickscan \
  --mode local \
  --type both \
  --input first_name=John last_name=Doe \
  --verbose

# In terminal 2: Watch DB updates
watch -n 1 'psql -c "SELECT target, status, COUNT(*) FROM scrape_results WHERE created_at > NOW() - INTERVAL 1h GROUP BY target, status;"'
```

---

## Migration & Setup

### First-Time Setup

1. **Apply migration** to create `scrape_results` table:
```bash
cd Vanyshr-mono
supabase migration up  # Or manually run: supabase/migrations/20260729_scrape_results.sql
```

2. **Verify table exists**:
```sql
SELECT * FROM scrape_results LIMIT 1;
```

3. **Set environment variables** (see [Environment Setup](#environment-setup))

4. **Run first scrape**:
```bash
python scrape_runner.py \
  --target fps \
  --mode local \
  --type summary \
  --input first_name=Test last_name=User city="San Francisco" state=CA
```

5. **Verify results in DB**:
```sql
SELECT scrape_id, target, status, response_time_ms 
FROM scrape_results 
ORDER BY created_at DESC 
LIMIT 5;
```

---

## Next Steps

- [ ] Run full QuickScan tests (all scrapers, both modes)
- [ ] Analyze performance metrics (response times, success rates)
- [ ] Compare results across scrapers for consistency
- [ ] Monitor blocking patterns and update workarounds
- [ ] Generate reports from `scrape_results` data
