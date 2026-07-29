# Vanyshr Scraper Quick Recall

## Scraper Targets

### Anywho Scraper
- **Worker:** `workers/anywho/`
- **Main Module:** `anywho_test.py`
- **Purpose:** Parse anywho.com people search results
- **Input:** name, city (optional), state (optional)
- **Output:** name, age, phones, address, aliases (AKA), related people, detail link
- **Test file:** `tests/test_anywho.py`
- **Test Status:** ✅ 46/46 PASSED

### ZabaSearch Relay
- **Worker:** `workers/zabasearch-relay/`
- **Purpose:** Forward ZabaSearch API calls (people search, background checks)
- **Input:** phone or name search parameters
- **Output:** Summary fields (first_name, last_name, age, addresses, phones, emails); full profile on demand
- **Test file:** `tests/test_zabasearch.py`
- **Test Status:** ✅ 46/46 PASSED

### Other Scrapers (Reference)
- **fps** — Fast-pass Playwright scraper (fps-playwright worker)
- **npd** — NPD reference data (npd worker)

## Test Users & Data

### ZabaSearch Test Input
```python
# Example test input
input_data = {
    "name": "John Smith",
    "city": "New York",
    "state": "NY"
}
```

### Expected Summary Output Fields
```python
{
    "first_name": str,
    "last_name": str,
    "age": int | None,
    "addresses": [{"street": str, "city": str, "state": str, "zip": str}],
    "phones": [{"number": str, "type": str}],
    "emails": [{"email": str}],
    "status": "success" | "no_results" | "error"
}
```

## Database Schema (Logging)

### scraper_results table
```sql
scraper_type: VARCHAR (fps, anywho, zabasearch, npd)
scrape_mode: VARCHAR (summary, full)
input_data: JSONB
summary_results: JSONB
full_profile_results: JSONB (nullable)
status: VARCHAR (success, failed, timeout, no_results)
metadata: JSONB
created_at: TIMESTAMP
```

## Test Patterns

### Running Anywho Tests
```bash
cd /Users/jameso/DevWork/vanyshr-stack/vanyshr-scrapers
pytest tests/test_anywho.py -v --cov
pytest tests/test_anywho.py::TestSlugify -v  # Single class
pytest tests/test_anywho.py::TestParseHtml::test_parse_single_result -v  # Single test
```

### Running ZabaSearch Tests
```bash
cd /Users/jameso/DevWork/vanyshr-stack/vanyshr-scrapers
pytest tests/test_zabasearch.py -v --cov
pytest tests/test_zabasearch.py::test_summary_search -v  # Single test
```

### Running All Tests
```bash
pytest tests/ -v --cov  # All tests with coverage
pytest tests/ -k "anywho" -v  # Filter by scraper name
```

### Logging Pattern (for manual testing)
```python
from scripts.log_scraper_results import log_scrape_result

log_scrape_result(
    scraper_type="anywho",
    scrape_mode="summary",
    input_data={"name": "John Doe", "city": "San Francisco", "state": "CA"},
    summary_results={"name": "John Doe", "age": "42", "phones": ["415-555-0123"]},
    full_profile_results=None,
    status="success",
    metadata={"source": "anywho.com", "test_env": "local"}
)
```

## Key Files to Reference
- **Anywho Tests:** `/vanyshr-scrapers/tests/test_anywho.py`
- **Anywho Worker:** `/vanyshr-scrapers/workers/anywho/anywho_test.py`
- **ZabaSearch Tests:** `/vanyshr-scrapers/tests/test_zabasearch.py`
- **ZabaSearch Worker:** `/vanyshr-scrapers/workers/zabasearch-relay/`
- **Shared Fixtures:** `/vanyshr-scrapers/tests/conftest.py` (mock HTML samples, HTTP mocks)
- **Logger:** `/vanyshr-scrapers/scripts/log_scraper_results.py`
- **Project Readme:** `/vanyshr-scrapers/README.md`
- **Testing Docs:** `/vanyshr-scrapers/tests/README.md`, `SCRAPE_RUNNER.md`, `LOGGING_INTEGRATION.md`
