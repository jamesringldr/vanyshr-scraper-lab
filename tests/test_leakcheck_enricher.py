"""
Data-quality tests for leakcheck_enricher against recorded API responses.

The free endpoint has several traps that only show up under load, so they are
pinned here rather than discovered in production:

  - HTTP 200 is returned for misses, invalid input and rate limiting alike, so
    the status code proves nothing
  - the rate-limit body is invalid JSON (Python's `False`), which makes
    json.loads raise precisely when the service is busiest
  - invalid addresses are indistinguishable from genuine misses

No network here: httpx.get is replaced with the recorded bodies.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import leakcheck_enricher as module  # noqa: E402
from leakcheck_enricher import LeakcheckEnricher  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "leakcheck"

pytestmark = pytest.mark.unit


def body(name):
    return (FIXTURES / f"{name}.json").read_text()


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


@pytest.fixture
def enricher():
    return LeakcheckEnricher(timeout=5)


@pytest.fixture
def respond(monkeypatch):
    """Serve a recorded body in place of a live call."""
    calls = []

    def install(fixture_name):
        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse(body(fixture_name))

        monkeypatch.setattr(module.httpx, "get", fake_get)
        return calls

    return install


class TestFoundResponse:
    def test_status_and_count(self, enricher, respond):
        respond("found")
        result = enricher.enrich_email("jaoehring@gmail.com")
        assert result["status"] == "success"
        assert result["breach_count"] == 8

    def test_breach_sources_parsed(self, enricher, respond):
        respond("found")
        sources = {b["source"] for b in enricher.enrich_email("a@b.com")["breaches"]}
        assert "Robinhood.com" in sources
        assert "Hautelook.com" in sources

    def test_dates_and_years(self, enricher, respond):
        respond("found")
        by_source = {b["source"]: b for b in enricher.enrich_email("a@b.com")["breaches"]}
        assert by_source["Robinhood.com"]["date"] == "2021-11"
        assert by_source["Robinhood.com"]["year"] == "2021"

    def test_most_recent_first(self, enricher, respond):
        respond("found")
        dates = [b["date"] for b in enricher.enrich_email("a@b.com")["breaches"]]
        assert dates == sorted(dates, reverse=True)

    def test_exposed_field_types(self, enricher, respond):
        respond("found")
        fields = enricher.enrich_email("a@b.com")["fields_exposed"]
        # The union across breaches -- what leaked, never the values
        assert "password" in fields and "dob" in fields
        assert fields == sorted(set(fields))

    def test_no_credential_values_returned(self, enricher, respond):
        respond("found")
        result = enricher.enrich_email("a@b.com")
        # fields_exposed names field *types*; nothing should carry a value
        assert all(isinstance(f, str) for f in result["fields_exposed"])
        for breach in result["breaches"]:
            assert set(breach) == {"source", "date", "year"}

    def test_second_fixture_has_different_fields(self, enricher, respond):
        respond("found_yahoo")
        result = enricher.enrich_email("rickioehring@yahoo.com")
        assert result["status"] == "success"
        assert "Yahoo.com" in {b["source"] for b in result["breaches"]}


class TestMisses:
    def test_not_found_is_not_an_error(self, enricher, respond):
        respond("not_found")
        result = enricher.enrich_email("ja_studly@hotmail.com")
        assert result["status"] == "not_found"
        assert result["breaches"] == []
        assert result["error"] is None

    def test_invalid_address_never_calls_the_api(self, enricher, respond):
        calls = respond("not_found")
        result = enricher.enrich_email("not-an-email")
        assert result["status"] == "invalid_email"
        assert calls == [], "invalid address should be screened before the request"

    @pytest.mark.parametrize("value", ["", "   ", "no-at-sign", "a@b", "@b.com"])
    def test_rejects_malformed_addresses(self, enricher, value):
        assert enricher.enrich_email(value)["status"] == "invalid_email"


class TestRateLimiting:
    """The case that crashes a naive client."""

    def test_rate_limit_body_is_invalid_json(self):
        raw = body("rate_limited")
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_parser_survives_invalid_json(self, enricher):
        parsed = enricher._loads(body("rate_limited"))
        assert parsed is not None
        assert parsed["success"] is False

    def test_rate_limit_is_reported_not_raised(self, enricher, respond):
        respond("rate_limited")
        result = enricher.enrich_email("a@b.com")
        assert result["status"] == "rate_limited"
        assert result["breaches"] == []

    def test_rate_limit_not_mistaken_for_a_miss(self, enricher, respond):
        """Reporting a quota failure as "no breaches found" would be a lie."""
        respond("rate_limited")
        assert enricher.enrich_email("a@b.com")["status"] != "not_found"

    def test_unparseable_body_is_an_error(self, enricher, monkeypatch):
        monkeypatch.setattr(
            module.httpx, "get", lambda url, **kw: FakeResponse("<html>502</html>")
        )
        assert enricher.enrich_email("a@b.com")["status"] == "error"


class TestBatch:
    def test_stops_once_rate_limited(self, enricher, monkeypatch):
        """
        Continuing past a quota failure would return rate-limit responses for
        the rest and make unchecked addresses look checked.
        """
        seen = []

        def fake_get(url, **kwargs):
            seen.append(kwargs["params"]["check"])
            name = "found" if len(seen) == 1 else "rate_limited"
            return FakeResponse(body(name))

        monkeypatch.setattr(module.httpx, "get", fake_get)
        monkeypatch.setattr(module.time, "sleep", lambda s: None)

        results = enricher.enrich_emails_batch(["a@b.com", "c@d.com", "e@f.com"])
        assert len(seen) == 2, "should stop at the first rate-limited response"
        assert results["a@b.com"]["status"] == "success"
        assert results["c@d.com"]["status"] == "rate_limited"
        assert "e@f.com" not in results

    def test_paces_calls(self, enricher, monkeypatch):
        delays = []
        monkeypatch.setattr(module.time, "sleep", lambda s: delays.append(s))
        monkeypatch.setattr(
            module.httpx, "get", lambda url, **kw: FakeResponse(body("not_found"))
        )
        enricher.enrich_emails_batch(["a@b.com", "c@d.com", "e@f.com"])
        # One pause between calls, none before the first
        assert len(delays) == 2
        assert all(d > 0 for d in delays)


class TestRequestShape:
    def test_sends_a_user_agent(self, enricher, respond):
        calls = respond("not_found")
        enricher.enrich_email("a@b.com")
        # Without one, Cloudflare answers 403
        assert "User-Agent" in calls[0][1]["headers"]

    def test_no_api_key_required(self):
        # The old implementation returned nothing unless LEAKCHECK_API_KEY was set
        result = LeakcheckEnricher(api_key=None)
        assert result is not None

    def test_api_key_argument_is_tolerated(self):
        """Existing callers pass one; it must not break them."""
        assert LeakcheckEnricher(api_key="ignored") is not None
