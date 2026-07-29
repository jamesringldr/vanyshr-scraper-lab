# Scraper Unit Tests

Comprehensive unit test suite for Vanyshr's people search scrapers.

## Overview

This directory contains pytest unit tests for:

1. **Anywho** (`test_anywho.py`) — anywho.com people search scraper
2. **FPS Playwright** (`test_fps_playwright.py`) — FastPeopleSearch browser automation
3. **Zabasearch Relay** (`test_zabasearch.py`) — Phone lookup via Zabasearch/Cloudflare Worker
4. **NPD** (`test_npd.py`, future) — National Public Data scraper (scaffold in progress)

All tests are **unit tests** — they use mocked HTTP responses and require no real network calls, making them fast and reliable.

## Running Tests

### Quick Start

```bash
# Run all tests
./run_tests.sh

# Run only unit tests (fast)
./run_tests.sh --fast

# Run with coverage report
./run_tests.sh --cov

# Run tests for specific scraper
./run_tests.sh -k anywho
./run_tests.sh -k zabasearch
./run_tests.sh -k fps

# Run in verbose mode
./run_tests.sh -v
```

### Manual pytest

If you prefer to run pytest directly:

```bash
# From this directory (tests/)
pytest                    # Run all
pytest -m unit            # Only unit tests
pytest test_anywho.py     # Specific file
pytest -k "test_slug"     # Specific test name
pytest -v --tb=short      # Verbose with short tracebacks
pytest --cov=.            # With coverage
```

## Test Structure

### Files

```
tests/
├── conftest.py              # Shared fixtures and mocks
├── pytest.ini               # Pytest configuration
├── run_tests.sh             # Test runner script
├── test_anywho.py           # Anywho scraper tests
├── test_fps_playwright.py   # FPS browser automation tests
├── test_zabasearch.py       # Zabasearch relay tests
└── README.md                # This file
```

### Test Organization

Each test file follows a similar structure:

```python
# Import/setup

class TestComponentName:
    """Test group for one component."""

    @pytest.mark.unit
    def test_specific_behavior(self, fixture_name):
        """Test description."""
        # Arrange: Set up test data
        # Act: Call the function
        # Assert: Verify result
        pass
```

## Test Coverage

### Anywho Tests (`test_anywho.py`)

- **URL Building** — slug formatting, state abbreviations, city/state combination
- **HTML Parsing** — name extraction, age, location, phones, aliases
- **Phone Reassembly** — reconstructing digits from blurred spans
- **Blocking Detection** — Cloudflare challenge detection
- **Edge Cases** — malformed HTML, invalid names, empty responses

### FPS Playwright Tests (`test_fps_playwright.py`)

- **URL Flow** — Google referral chain, FPS navigation
- **Result Parsing** — name, age, location, phone extraction from output
- **Bot Detection** — Turnstile, reCAPTCHA challenge handling
- **Fingerprinting** — Firefox UA, WebGL noise, cursor humanization
- **Environment Variables** — LOCAL_HEADED, NATIVE_FP, GEOIP configuration
- **Output Validation** — file generation, stage snapshots
- **Error Handling** — timeouts, missing arguments, UTF-8 encoding

### Zabasearch Tests (`test_zabasearch.py`)

- **Phone Normalization** — format validation, +1 stripping, digit extraction
- **HTML Parsing** — field extraction (name, age, address, phones, etc.)
- **Response Structure** — JSON schema validation, required fields
- **CORS Headers** — origin, methods, headers validation
- **Authentication** — relay token validation, header/param support
- **URL Validation** — domain whitelisting (zabasearch, FPS, anywho)
- **Endpoint Routing** — /phone, /relay, OPTIONS handling

## Fixtures

### HTML Samples (from `conftest.py`)

```python
# anywho samples
anywho_html_sample         # Valid result with one person
anywho_html_no_results     # Empty results page
anywho_html_blocked        # Cloudflare challenge page

# zabasearch samples
zabasearch_html_sample     # Valid phone lookup result
zabasearch_html_no_result  # Phone not found

# fps samples
fps_smoke_success          # Successful search output
fps_smoke_blocked          # Blocked/challenged output
```

### Mock Factories

```python
mock_http_get()            # Mock urllib.request.urlopen
mock_fetch()               # Mock browser fetch()
mock_response_factory      # Factory for creating mock responses
```

### Utilities

```python
assert_record()            # Validate person data structure
```

## Adding New Tests

### For Existing Scrapers

1. Open `test_<scraper>.py`
2. Add a new test class or method following the naming convention
3. Use existing fixtures or create new ones in `conftest.py`
4. Mark with `@pytest.mark.unit` for unit tests

Example:

```python
@pytest.mark.unit
def test_my_new_feature(self, anywho_html_sample):
    """Test description."""
    results = parse(anywho_html_sample)
    assert len(results) > 0
```

### For NPD Scraper (When Implemented)

Once NPD API details are available:

1. Update `workers/npd/npd_scraper.py` with implementation
2. Add mock response data to `conftest.py` (NPD_SAMPLE_HTML or JSON)
3. Create `test_npd.py` following the same pattern as other scrapers
4. Run `./run_tests.sh --fast` to verify

## Test Data

All test data is defined in `conftest.py` to avoid brittle HTML/JSON dependencies:

- **ANYWHO_SAMPLE_HTML** — Minimal valid result page
- **ANYWHO_NO_RESULTS_HTML** — Empty results
- **ANYWHO_BLOCKED_HTML** — Cloudflare challenge
- **ZABASEARCH_SAMPLE_HTML** — Complete phone lookup result
- **ZABASEARCH_NO_RESULT_HTML** — Phone not found
- **FPS_SMOKE_SUCCESS_OUTPUT** — Successful search output
- **FPS_SMOKE_BLOCKED_OUTPUT** — Blocked search output

To modify test data:

1. Edit the constant in `conftest.py`
2. Re-run tests to verify they still pass
3. Commit the updated fixture

## Markers

Tests are organized by marker:

```bash
# Run only unit tests (no network, mocked)
pytest -m unit

# Run only integration tests (may need network)
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run everything
pytest                    # Default includes all markers
```

## Coverage

To generate a coverage report:

```bash
./run_tests.sh --cov

# Or manually:
pytest --cov=. --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

**Goal**: Aim for 80%+ coverage on scraper logic (excluding browser automation, network I/O).

## Debugging

### Run a Single Test

```bash
pytest test_anywho.py::TestSlugify::test_slug_lowercase -vv
```

### Show Print Statements

```bash
pytest -vv -s test_anywho.py::TestSlugify::test_slug_lowercase
```

### Drop Into Debugger

```python
def test_something():
    result = parse(html)
    breakpoint()  # Drops into pdb
    assert result
```

Then run:

```bash
pytest -vv -s test_anywho.py::test_something
```

### Verbose Output

```bash
pytest -vv --tb=long test_anywho.py
```

## CI/CD Integration

To run tests in CI (GitHub Actions, etc.):

```yaml
- name: Run scraper tests
  run: |
    pip install pytest pytest-cov
    cd tests/
    ./run_tests.sh --cov
```

## Dependencies

### Required

- **Python 3.8+**
- **pytest** — test framework
- **pytest-cov** (optional) — coverage reporting

Install:

```bash
pip install pytest pytest-cov
```

### Not Required

- **Camoufox** — Only needed for actual FPS browser automation (not unit tests)
- **Cloudflare Wrangler** — Only needed to deploy zabasearch-relay Worker
- **Deno** — Only for TypeScript edge function tests

## Troubleshooting

### `ModuleNotFoundError: No module named 'anywho_test'`

This means the import path is wrong. The tests add `workers/anywho` to `sys.path`:

```python
sys.path.insert(0, str(workers_path / "anywho"))
from anywho_test import build_url, parse, ...
```

Make sure you're running from the `tests/` directory:

```bash
cd tests/
./run_tests.sh
```

### Fixtures Not Found

Make sure `conftest.py` is in the same directory as your test file, or pytest will auto-discover it.

### Import Issues

If tests can't import scraper functions:

1. Check that the function is exported in the scraper file
2. Verify the import statement in the test file
3. Run `pytest --collect-only` to see what pytest discovered

## Next Steps

### NPD Scraper

When API details are available:

1. ✅ Scaffold created in `workers/npd/`
2. ⏳ Fill in `workers/npd/npd_scraper.py` with implementation
3. ⏳ Create `tests/test_npd.py` with unit tests
4. ⏳ Add to `scripts/test-quickscan.sh` integration test

See `workers/npd/SPEC.md` for required configuration.

### Integration Tests

To add integration tests (actual network calls):

1. Create `test_*_integration.py` files
2. Mark with `@pytest.mark.integration`
3. Run only when needed: `pytest -m integration`
4. Document any external dependencies (API keys, etc.)

### Performance

Optimize slow tests:

```bash
pytest --durations=10  # Show 10 slowest tests
```

## Contributing

When adding new tests:

1. Follow the existing class/method naming convention
2. Use docstrings for test descriptions
3. Mark unit tests with `@pytest.mark.unit`
4. Add fixtures to `conftest.py`, not inline
5. Update this README if adding new test categories

## References

- **Anywho Scraper** — `workers/anywho/anywho_test.py`
- **FPS Scraper** — `workers/fps-playwright/smoke.py`
- **Zabasearch Worker** — `workers/zabasearch-relay/src/index.ts`
- **Quickscan Tests** — `scripts/test-quickscan.sh`
- **NPD Scaffold** — `workers/npd/SPEC.md`

---

**Last Updated**: 2026-07-28
**Test Count**: ~150 unit tests across 4 scrapers
**Coverage Target**: 80%+ on logic layer
