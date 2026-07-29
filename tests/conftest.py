"""
Shared pytest configuration and fixtures for scraper tests.

Includes:
  - Mock HTTP responses (anywho, FPS, Zabasearch)
  - HTML/JSON test data fixtures
  - Mock network isolation (no real HTTP calls)
  - Common utilities for assertion and test setup
  - Automatic database logging via pytest hook
"""

# Load .env.local before anything else
import os
from pathlib import Path

def _load_env():
    """Load .env.local from various locations."""
    # vanyshr-scrapers/tests is at: .../vanyshr-stack/vanyshr-scrapers/tests
    # .env.local is at: .../vanyshr-stack/Vanyshr-mono/.env.local

    test_dir = Path(__file__).resolve().parent

    # Candidates (in order of preference)
    candidates = [
        test_dir.parent.parent / "Vanyshr-mono" / ".env.local",  # Sibling at vanyshr-stack level
        test_dir.parent.parent.parent / ".env.local",  # vanyshr-stack root
        test_dir / ".env.local",  # tests directory itself
        test_dir.parent / ".env.local",  # vanyshr-scrapers
    ]

    for env_file in candidates:
        if env_file.exists():
            try:
                import dotenv
                dotenv.load_dotenv(env_file)
            except ImportError:
                # If python-dotenv not available, manually load
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            os.environ[key.strip()] = val.strip()
            break

_load_env()

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


# ─── Mock Response Data ────────────────────────────────────────────────────────

ANYWHO_SAMPLE_HTML = """
<html>
<body>
  <div class="card">
    <h2>John Doe</h2>
    <h3>Age 42</h3>
    <h3>Lives in: San Francisco, CA</h3>
    <h3>Phone Number:
      <span data-content="415">•••</span>-
      <span data-content="555">•••</span>-
      <span data-content="0123">••••</span>
    </h3>
    <h3>AKA: Johnny Doe</h3>
    <h3>Related to: Jane Doe</h3>
    <a href="/people/a12345">View Details</a>
  </div>
</body>
</html>
"""

ANYWHO_NO_RESULTS_HTML = """
<html>
<body>
  <h2>No results found for John Doe</h2>
  <p>Try searching with a different name or location.</p>
</body>
</html>
"""

ANYWHO_BLOCKED_HTML = """
<html>
<body>
  <title>Just a moment...</title>
  <p>Checking your browser before accessing the website.</p>
</body>
</html>
"""

ZABASEARCH_SAMPLE_HTML = """
<html>
<body>
  <div id="result-top-content">
    <h3>John Doe</h3>
    <table>
      <tr><th>Age</th><td>42</td></tr>
      <tr><th>Birth Year</th><td>1982</td></tr>
      <tr><th>Line Type</th><td>Landline</td></tr>
      <tr><th>Carrier</th><td>AT&T</td></tr>
      <tr><th>Location</th><td>San Francisco, CA</td></tr>
      <tr><th>Time Zone</th><td>Pacific</td></tr>
    </table>
  </div>

  <div id="phone-number-names">
    <ul>
      <li>Johnny Doe</li>
      <li>J.D.</li>
    </ul>
  </div>

  <div id="phone-number-locations">
    <h5>Most Recent Address</h5>
    <ul>
      <li>123 Main St, San Francisco, CA 94102</li>
    </ul>
    <h5>Previous Addresses</h5>
    <ul>
      <li>456 Oak Ave, Oakland, CA 94601</li>
    </ul>
  </div>

  <div id="phone-number-previous">
    <ul>
      <li>415-555-0124</li>
    </ul>
  </div>

  <div id="phone-number-related">
    <ul>
      <li><a href="/person/jane-doe">Jane Doe</a></li>
    </ul>
  </div>
</body>
</html>
"""

ZABASEARCH_NO_RESULT_HTML = """
<html>
<body>
  <p>No results found for this phone number.</p>
</body>
</html>
"""

FPS_SMOKE_SUCCESS_OUTPUT = """
✅ 2 result card(s):
[1] John Doe, Age 42
    Lives in:     San Francisco, CA
    Phones:       415-555-0123
    Details:      https://www.fastpeoplesearch.com/name/john-doe
"""

FPS_SMOKE_BLOCKED_OUTPUT = """
⛔ blocked / empty response (402 bytes) —
Checking your browser before accessing the website.
"""


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def anywho_html_sample():
    """Sample anywho.com result page with one person card."""
    return ANYWHO_SAMPLE_HTML


@pytest.fixture
def anywho_html_no_results():
    """Sample anywho.com page with no results."""
    return ANYWHO_NO_RESULTS_HTML


@pytest.fixture
def anywho_html_blocked():
    """Sample anywho.com page blocked by Cloudflare."""
    return ANYWHO_BLOCKED_HTML


@pytest.fixture
def zabasearch_html_sample():
    """Sample zabasearch.com phone lookup result page."""
    return ZABASEARCH_SAMPLE_HTML


@pytest.fixture
def zabasearch_html_no_result():
    """Sample zabasearch.com page with no results."""
    return ZABASEARCH_NO_RESULT_HTML


@pytest.fixture
def fps_smoke_success():
    """Sample FPS smoke test success output."""
    return FPS_SMOKE_SUCCESS_OUTPUT


@pytest.fixture
def fps_smoke_blocked():
    """Sample FPS smoke test blocked output."""
    return FPS_SMOKE_BLOCKED_OUTPUT


@pytest.fixture
def mock_http_get():
    """
    Fixture to mock urllib.request with custom response.

    Usage:
        def test_something(mock_http_get):
            mock_http_get.return_value = "html content"
            # call function that does HTTP GET
    """
    with patch("urllib.request.urlopen") as mock:
        response_mock = MagicMock()
        response_mock.read.return_value = b"<html></html>"
        response_mock.__enter__.return_value = response_mock
        mock.return_value = response_mock
        yield mock


@pytest.fixture
def mock_fetch():
    """
    Fixture to mock fetch() calls (for browser-based scrapers).

    Usage:
        def test_something(mock_fetch):
            mock_fetch.return_value = Mock(status=200, text="<html></html>")
            # call function that uses fetch
    """
    with patch("builtins.fetch") as mock:
        mock.return_value = MagicMock(
            status=200,
            text="<html></html>",
            ok=True
        )
        yield mock


class MockResponse:
    """Helper mock response object for testing."""

    def __init__(self, content, status=200, headers=None):
        self.content = content
        self.text = content if isinstance(content, str) else content.decode()
        self.status = status
        self.ok = 200 <= status < 300
        self.headers = headers or {}

    def json(self):
        """Parse response as JSON."""
        return json.loads(self.text)

    async def text(self):
        """Return text (async version)."""
        return self.text


@pytest.fixture
def mock_response_factory():
    """
    Factory to create mock responses easily.

    Usage:
        def test_something(mock_response_factory):
            resp = mock_response_factory(ANYWHO_SAMPLE_HTML, status=200)
            assert resp.ok
    """
    return MockResponse


# ─── Markers for test categorization ──────────────────────────────────────────

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "unit: unit test (no network, uses mocks)",
    )
    config.addinivalue_line(
        "markers",
        "integration: integration test (may need network or external services)",
    )
    config.addinivalue_line(
        "markers",
        "slow: slow test (avoid during rapid iteration)",
    )


# ─── Test utilities ────────────────────────────────────────────────────────────

def assert_person_record(record):
    """
    Validate that a record has the expected person data structure.

    All scrapers should return dicts with these optional fields:
      - name (str)
      - age (str or int)
      - aliases (list of str)
      - phones (list of str)
      - addresses (list of str)
      - relatives (list of str)
      - detail_link (str)
      - source (str) — scraper name
    """
    assert isinstance(record, dict), "Record must be a dict"
    assert "name" in record or "source" in record, "Record must have name or source"

    # Validate field types if present
    if "age" in record:
        assert isinstance(record["age"], (str, int, type(None)))
    if "aliases" in record:
        assert isinstance(record["aliases"], list)
    if "phones" in record:
        assert isinstance(record["phones"], list)
    if "addresses" in record:
        assert isinstance(record["addresses"], list)
    if "relatives" in record:
        assert isinstance(record["relatives"], list)
    if "detail_link" in record:
        assert isinstance(record["detail_link"], (str, type(None)))
    if "source" in record:
        assert isinstance(record["source"], str)


@pytest.fixture
def assert_record():
    """Fixture to use assert_person_record in tests."""
    return assert_person_record


# ─── Automatic Database Logging ────────────────────────────────────────────────

def pytest_configure(config):
    """Configure pytest and set up logging."""
    # Global flag to track if logging is enabled
    config.log_results = config.getoption("--log-results", default=False)


def pytest_addoption(parser):
    """Add command-line options."""
    parser.addoption(
        "--log-results",
        action="store_true",
        default=False,
        help="Automatically log test results to Supabase"
    )


def _parse_test_metadata(item):
    """
    Extract scraper type and scrape mode from test item.

    Examples:
        test_anywho_parse_summary → scraper=anywho, mode=summary
        test_fps_playwright_parse → scraper=fps, mode=full_profile (default)
        TestAnywho::test_parse_summary → scraper=anywho, mode=summary
    """
    test_name = item.name.lower()

    # Extract scraper type from test name or file name
    scraper_map = {
        "anywho": "anywho",
        "fps": "fps",
        "zabasearch": "zabasearch",
        "zaba": "zabasearch",
        "npd": "npd",
    }

    scraper_type = None
    for key, scraper in scraper_map.items():
        if key in test_name or key in item.fspath.basename.lower():
            scraper_type = scraper
            break

    # Extract scrape mode (summary or full_profile)
    scrape_mode = "full_profile"  # default
    if "summary" in test_name:
        scrape_mode = "summary"

    # Check for marker
    if item.get_closest_marker("summary"):
        scrape_mode = "summary"
    elif item.get_closest_marker("full_profile"):
        scrape_mode = "full_profile"

    return scraper_type, scrape_mode


def _extract_fixture_data(item):
    """Extract input/output data from test fixtures."""
    data = {}

    # Capture fixture values passed to test
    for fixture_name in item.fixturenames:
        if fixture_name.endswith("_sample") or fixture_name.endswith("_html"):
            # Skip large HTML fixtures
            continue
        fixture_value = item.funcargs.get(fixture_name)
        if isinstance(fixture_value, (str, int, float, bool, dict, list)):
            data[fixture_name] = fixture_value

    return data


def pytest_runtest_makereport(item, call):
    """
    Pytest hook called after each test.
    Automatically logs results to Supabase if --log-results flag is set.
    """
    # Only log on test teardown (when we have full result)
    if call.when != "teardown":
        return

    # Check if logging is enabled
    config = item.config
    if not hasattr(config, "log_results") or not config.log_results:
        return

    # Skip if not a scraper test
    scraper_type, scrape_mode = _parse_test_metadata(item)
    if not scraper_type:
        return

    try:
        # Try to import logger, add current directory to path if needed
        try:
            from log_scraper_results import log_scrape_result
        except ImportError:
            import sys
            from pathlib import Path
            tests_dir = str(Path(__file__).parent)
            if tests_dir not in sys.path:
                sys.path.insert(0, tests_dir)
            from log_scraper_results import log_scrape_result
    except ImportError as e:
        # Silent fail if logger not available (just skip logging)
        return

    # Get test outcome from call result
    if call.excinfo:
        status = "error" if call.excinfo.type == Exception else "failed"
        error_message = str(call.excinfo.value)[:500]
    else:
        status = "success"
        error_message = None

    # Extract fixture data (input/output)
    fixture_data = _extract_fixture_data(item)

    # Determine input_data from test node
    input_data = {
        "test_name": item.name,
        "test_class": item.cls.__name__ if item.cls else None,
        **fixture_data
    }

    # Log the result
    log_scrape_result(
        scraper_type=scraper_type,
        scrape_mode=scrape_mode,
        input_data=input_data,
        summary_results=None,  # Unit tests don't have actual scrape results
        full_profile_results=None,
        status=status,
        error_message=error_message,
        execution_time_ms=int(call.duration * 1000) if call.duration else 0,
        notes=f"Pytest unit test: {item.fspath.basename}::{item.name}"
    )
