# Automatic Database Logging Integration

Pytest test results are automatically logged to Supabase using a pytest hook in `conftest.py`.

---

## How It Works

### Architecture

```
pytest runs tests
    ↓
pytest_runtest_makereport hook (in conftest.py)
    ↓
_parse_test_metadata() extracts: scraper_type, scrape_mode
    ↓
_extract_fixture_data() captures: test inputs/outputs
    ↓
log_scrape_result() writes to database
    ↓
Supabase table: scraper_test_results
```

### Key Components

**1. Pytest Hook (`pytest_runtest_makereport`)**
- Called after every test completes
- Captures test status (passed/failed/error)
- Extracts execution time
- Triggers logging

**2. Metadata Parsing (`_parse_test_metadata`)**
- Reads test name to determine scraper type
- Looks for "summary" or "full_profile" in test name
- Supports pytest markers: `@pytest.mark.summary`, `@pytest.mark.full_profile`

**3. Fixture Data Extraction (`_extract_fixture_data`)**
- Collects data from test fixtures
- Skips large HTML fixtures
- Passes to logger as `input_data`

**4. Logging Call**
- Happens automatically after each test teardown
- Includes: scraper type, mode, status, error message, execution time
- Marks tests as "unit test" results

---

## Usage

### Enable Logging

```bash
# Run tests with automatic logging
cd /vanyshr-scrapers/tests
./run_tests.sh --log

# Or manually with pytest
pytest test_anywho.py --log-results
```

### Without Logging (default)

```bash
# Normal test run (no logging)
./run_tests.sh
pytest test_anywho.py -v
```

### Combine Options

```bash
# Fast tests with logging and coverage
./run_tests.sh --fast --log --cov

# Single scraper with logging
./run_tests.sh -k anywho --log
```

---

## What Gets Logged

### Every Test Results In

```json
{
  "scraper_type": "anywho|fps|zabasearch|npd",
  "scrape_mode": "summary|full_profile",
  "input_data": {
    "test_name": "test_slug_lowercase",
    "test_class": "TestSlugify",
    "fixture_1": "value_1"
  },
  "status": "success|failed|error",
  "error_message": "AssertionError: ... (if failed)",
  "execution_time_ms": 45,
  "notes": "Pytest unit test: test_anywho.py::TestSlugify::test_slug_lowercase"
}
```

### Example Logged Test

```
Test: test_anywho_parse_summary

Logged as:
{
  "scraper_type": "anywho",
  "scrape_mode": "summary",
  "input_data": {
    "test_name": "test_parse_single_result",
    "test_class": "TestParseHtml",
    "anywho_html_sample": "[HTML fixture content preview]"
  },
  "status": "success",
  "execution_time_ms": 12,
  "notes": "Pytest unit test: test_anywho.py::TestParseHtml::test_parse_single_result"
}
```

---

## Customizing Logging

### Skip Logging for Specific Tests

```python
@pytest.mark.no_log  # Not yet implemented, but can be added
def test_slow_expensive_operation():
    pass
```

### Mark Tests for Specific Mode

```python
class TestAnywho:
    @pytest.mark.summary
    def test_quick_lookup(self):
        """Logged as scrape_mode='summary'"""
        pass

    @pytest.mark.full_profile
    def test_deep_scrape(self):
        """Logged as scrape_mode='full_profile'"""
        pass
```

### Manual Logging in Tests

For tests that do actual scraping (not mocked), manually log results:

```python
from log_scraper_results import log_scrape_result

def test_live_anywho_scrape():
    """Test actual scraper, not mocked."""
    results = anywho_search("John", "Doe", "SF", "CA")
    
    # Test assertions
    assert results is not None
    
    # Manual logging of actual results
    log_scrape_result(
        scraper_type="anywho",
        scrape_mode="summary",
        input_data={"first_name": "John", "last_name": "Doe", "city": "SF", "state": "CA"},
        summary_results=results,
        status="success" if results else "no_results",
        execution_time_ms=245
    )
```

---

## Querying Logged Results

### Via Python

```python
from log_scraper_results import ScraperResultsLogger

logger = ScraperResultsLogger()

# Get all anywho tests
results = logger.get_results(scraper_type="anywho")

# Get only failed tests
failed = logger.get_results(status="failed")

# Get FPS summary tests
fps_summary = logger.get_results(
    scraper_type="fps",
    scrape_mode="summary"
)

for result in fps_summary:
    print(f"{result['created_at']}: {result['status']}")
```

### Via Supabase SQL

```sql
-- All logged tests
SELECT * FROM scraper_test_results ORDER BY created_at DESC LIMIT 20;

-- Tests by scraper
SELECT scraper_type, COUNT(*), SUM(CASE WHEN status='success' THEN 1 ELSE 0 END)
FROM scraper_test_results
GROUP BY scraper_type;

-- Failed tests
SELECT * FROM scraper_test_results WHERE status = 'failed' OR status = 'error';

-- Recent anywho tests
SELECT created_at, scrape_mode, status, execution_time_ms
FROM scraper_test_results
WHERE scraper_type = 'anywho'
ORDER BY created_at DESC
LIMIT 50;
```

---

## Environment Setup

For logging to work, you need:

1. **Supabase credentials** (in `.env.local`):
   ```env
   SUPABASE_URL=https://...
   SUPABASE_ANON_KEY=eyJ...
   ```

2. **Python dependencies**:
   ```bash
   pip install pytest supabase
   ```

3. **Database table** (already created):
   ```
   scraper_test_results table in vanyshr-mono Supabase project
   ```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'supabase'"
```bash
pip install supabase
```

### "No results logged, but tests ran"
Check:
1. Did you use `--log` flag? (e.g., `./run_tests.sh --log`)
2. Is `SUPABASE_URL` set in `.env.local`?
3. Run: `python -c "from supabase import create_client; print('OK')"`

### "Tests slow down with logging"
Logging adds ~5-10ms per test (database write). If too slow:
- Use `--log` selectively for specific scrapers
- Run unit tests without logging, manual logging for integration tests

### Credentials Error
```
ERROR: 401 Unauthorized
```
Check `.env.local`:
- `SUPABASE_URL` is correct URL
- `SUPABASE_ANON_KEY` is valid (not the service role key)
- Keys have no extra spaces or newlines

---

## Best Practices

✅ **DO**
- Run `./run_tests.sh --log --fast` regularly to build a test history
- Query results to track coverage and failures over time
- Use meaningful test names (include scraper type + mode)
- Log both unit tests and integration tests

❌ **DON'T**
- Force logging on slow network (adds latency)
- Log during CI unless you need the history
- Store secrets in test code (use `.env.local`)
- Disable logging for unit tests you want to track

---

## Examples

### Run All Tests with Logging

```bash
cd /vanyshr-scrapers/tests
./run_tests.sh --log
```

**Output:**
```
Running: pytest --tb=short -v --log-results
test_anywho.py::TestSlugify::test_slug_lowercase PASSED ✅ [logged]
test_anywho.py::TestSlugify::test_slug_spaces_to_dash PASSED ✅ [logged]
test_fps_playwright.py::TestFpsUrlBuilding::test_google_referral_url PASSED ✅ [logged]
...
```

### Quick Test Specific Scraper with Logging

```bash
./run_tests.sh -k zabasearch --log
```

### Test with Full Reporting

```bash
./run_tests.sh --fast --log --cov
```

---

## Future Enhancements

Potential improvements:

1. **Batch logging** — Collect all test results, log once at end (faster)
2. **Conditional logging** — Only log failed tests or slow tests
3. **Detailed output** — Print logging status as tests run
4. **Dashboard** — Supabase dashboard showing test history
5. **Alerts** — Notify if failure rate increases
6. **Performance tracking** — Graph execution time over time

---

## Reference

- **Pytest hooks**: https://docs.pytest.org/en/latest/how-to/writing_plugins.html#hook-specifications
- **Supabase Python**: https://supabase.com/docs/reference/python/introduction
- **Database schema**: `scraper_test_results` table in vanyshr-mono
