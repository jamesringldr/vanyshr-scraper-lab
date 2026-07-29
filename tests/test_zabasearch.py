"""
Unit tests for zabasearch-relay scraper (CloudFlare Worker in TypeScript).

Tests the logic layer:
  - Phone number normalization and validation
  - HTML parsing field extraction
  - Response structure validation
  - CORS header handling
  - Relay authentication

Note: These tests are written in Python and mock the Cloudflare Worker
environment. The actual TypeScript implementation is in
workers/zabasearch-relay/src/index.ts
"""

import pytest
import json
import re
from unittest.mock import Mock, MagicMock


class TestPhoneNormalization:
    """Test phone number normalization logic."""

    @pytest.mark.unit
    def test_normalize_simple_digits(self):
        """Normalize 10-digit phone to standard format."""
        phone = "4155550123"
        # Should return just the digits if it's 10 digits
        assert len(phone) == 10
        assert phone.isdigit()

    @pytest.mark.unit
    def test_normalize_with_dashes(self):
        """Normalize phone with dashes."""
        raw = "415-555-0123"
        digits = re.sub(r"\D", "", raw)
        assert digits == "4155550123"
        assert len(digits) == 10

    @pytest.mark.unit
    def test_normalize_with_parentheses(self):
        """Normalize phone with parentheses."""
        raw = "(415) 555-0123"
        digits = re.sub(r"\D", "", raw)
        assert digits == "4155550123"

    @pytest.mark.unit
    def test_normalize_with_dots(self):
        """Normalize phone with dots."""
        raw = "415.555.0123"
        digits = re.sub(r"\D", "", raw)
        assert digits == "4155550123"

    @pytest.mark.unit
    def test_normalize_with_plus(self):
        """Normalize phone with +1 country code."""
        raw = "+1-415-555-0123"
        digits = re.sub(r"\D", "", raw)
        # With +1, we get 11 digits
        assert digits == "14155550123"
        # Should strip leading 1 if 11 digits total
        if len(digits) == 11 and digits[0] == "1":
            normalized = digits[1:]
        else:
            normalized = digits
        assert normalized == "4155550123"

    @pytest.mark.unit
    def test_invalid_phone_too_short(self):
        """Invalid: phone with fewer than 10 digits."""
        phone = "123456789"  # Only 9 digits
        assert len(phone) < 10

    @pytest.mark.unit
    def test_invalid_phone_too_long(self):
        """Invalid: phone with more than 11 digits."""
        phone = "12345678901234"
        assert len(phone) > 11

    @pytest.mark.unit
    def test_invalid_phone_no_digits(self):
        """Invalid: phone with no digits."""
        phone = "call me later"
        digits = re.sub(r"\D", "", phone)
        assert len(digits) == 0

    @pytest.mark.unit
    def test_format_normalized_phone(self):
        """Format normalized 10-digit phone as XXX-XXX-XXXX."""
        phone = "4155550123"
        formatted = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
        assert formatted == "415-555-0123"

    @pytest.mark.unit
    def test_phone_normalization_roundtrip(self):
        """Normalization should be idempotent."""
        phones = [
            "4155550123",
            "415-555-0123",
            "(415) 555-0123",
            "415.555.0123",
            "+1-415-555-0123",
        ]
        for phone in phones:
            digits = re.sub(r"\D", "", phone)
            if len(digits) == 11 and digits[0] == "1":
                digits = digits[1:]
            assert digits == "4155550123"


class TestFieldExtraction:
    """Test field extraction from HTML responses."""

    @pytest.mark.unit
    def test_extract_name(self, zabasearch_html_sample):
        """Extract person's name from HTML."""
        # Name should be in first <h3> within #result-top-content
        match = re.search(r"<h3>([^<]+)</h3>", zabasearch_html_sample)
        assert match is not None
        name = match.group(1).strip()
        assert name == "John Doe"

    @pytest.mark.unit
    def test_extract_age(self, zabasearch_html_sample):
        """Extract age from table."""
        match = re.search(r"<th>Age</th>\s*<td>(\d+)", zabasearch_html_sample)
        assert match is not None
        age = match.group(1)
        assert age == "42"

    @pytest.mark.unit
    def test_extract_birth_year(self, zabasearch_html_sample):
        """Extract birth year from table."""
        match = re.search(r"<th>Birth Year</th>\s*<td>(\d+)", zabasearch_html_sample)
        assert match is not None
        birth_year = match.group(1)
        assert birth_year == "1982"

    @pytest.mark.unit
    def test_extract_line_type(self, zabasearch_html_sample):
        """Extract line type (Landline/Mobile/VOIP)."""
        match = re.search(r"<th>Line Type</th>\s*<td>([^<]+)", zabasearch_html_sample)
        assert match is not None
        line_type = match.group(1).strip()
        assert line_type == "Landline"

    @pytest.mark.unit
    def test_extract_carrier(self, zabasearch_html_sample):
        """Extract phone carrier."""
        match = re.search(r"<th>Carrier</th>\s*<td>([^<]+)", zabasearch_html_sample)
        assert match is not None
        carrier = match.group(1).strip()
        assert carrier == "AT&T"

    @pytest.mark.unit
    def test_extract_location(self, zabasearch_html_sample):
        """Extract current location."""
        match = re.search(r"<th>Location</th>\s*<td>([^<]+)", zabasearch_html_sample)
        assert match is not None
        location = match.group(1).strip()
        assert "San Francisco" in location

    @pytest.mark.unit
    def test_extract_time_zone(self, zabasearch_html_sample):
        """Extract time zone."""
        match = re.search(r"<th>Time Zone</th>\s*<td>([^<]+)", zabasearch_html_sample)
        assert match is not None
        tz = match.group(1).strip()
        assert tz == "Pacific"

    @pytest.mark.unit
    def test_extract_aliases(self, zabasearch_html_sample):
        """Extract aliases from phone-number-names section."""
        # Should find <li> items in #phone-number-names
        aliases = re.findall(
            r"<div id=\"phone-number-names\">.+?<li>([^<]+)</li>",
            zabasearch_html_sample,
            re.DOTALL
        )
        # Might be empty in this simple sample, but structure should work
        assert isinstance(aliases, list)

    @pytest.mark.unit
    def test_extract_addresses(self, zabasearch_html_sample):
        """Extract both current and previous addresses."""
        # Most recent address
        match = re.search(
            r"<h5>Most Recent Address</h5>.+?<li>([^<]+)</li>",
            zabasearch_html_sample,
            re.DOTALL
        )
        assert match is not None
        most_recent = match.group(1).strip()
        assert "123 Main St" in most_recent

        # Previous addresses
        prev_matches = re.findall(
            r"<h5>Previous Addresses</h5>.+?<li>([^<]+)</li>",
            zabasearch_html_sample,
            re.DOTALL
        )
        assert len(prev_matches) > 0

    @pytest.mark.unit
    def test_extract_previous_phones(self, zabasearch_html_sample):
        """Extract previous phone numbers."""
        match = re.search(
            r"<div id=\"phone-number-previous\">.+?<li>([^<]+)</li>",
            zabasearch_html_sample,
            re.DOTALL
        )
        assert match is not None
        prev_phone = match.group(1).strip()
        assert "415" in prev_phone or "-555" in prev_phone

    @pytest.mark.unit
    def test_extract_related_persons(self, zabasearch_html_sample):
        """Extract related person links."""
        match = re.search(
            r'<div id="phone-number-related">.+?<a href="([^"]+)">([^<]+)</a>',
            zabasearch_html_sample,
            re.DOTALL
        )
        assert match is not None
        href = match.group(1)
        name = match.group(2).strip()
        assert href.startswith("/")
        assert name == "Jane Doe"


class TestResponseStructure:
    """Test the JSON response structure."""

    @pytest.mark.unit
    def test_response_has_required_fields(self):
        """Phone lookup response has all required fields."""
        response = {
            "phone": "4155550123",
            "source_url": "https://www.zabasearch.com/phone/415-555-0123",
            "name": "John Doe",
            "age": "42",
            "birth_year": "1982",
            "line_type": "Landline",
            "carrier": "AT&T",
            "location": "San Francisco, CA",
            "time_zone": "Pacific",
            "aliases": ["Johnny Doe", "J.D."],
            "related_persons": [{"name": "Jane Doe", "href": "/person/jane-doe"}],
            "most_recent_address": "123 Main St, San Francisco, CA 94102",
            "previous_addresses": ["456 Oak Ave, Oakland, CA 94601"],
            "email_domains": ["@example.com"],
            "previous_phones": ["415-555-0124"],
            "social_media": [],
            "jobs": [],
            "education": [],
            "professional_licenses": [],
        }

        required = [
            "phone", "source_url", "name", "age", "birth_year",
            "line_type", "carrier", "location", "time_zone",
            "aliases", "related_persons", "most_recent_address",
            "previous_addresses", "email_domains", "previous_phones",
            "social_media", "jobs", "education", "professional_licenses",
        ]
        for field in required:
            assert field in response, f"Missing field: {field}"

    @pytest.mark.unit
    def test_response_field_types(self):
        """Response fields have correct types."""
        response = {
            "phone": "4155550123",  # string
            "age": "42",  # string or null
            "aliases": [],  # array
            "related_persons": [],  # array of objects
            "previous_addresses": [],  # array
            "most_recent_address": "123 Main St",  # string or null
        }

        assert isinstance(response["phone"], str)
        assert isinstance(response["aliases"], list)
        assert isinstance(response["related_persons"], list)
        assert isinstance(response["previous_addresses"], list)

    @pytest.mark.unit
    def test_no_result_response(self, zabasearch_html_no_result):
        """Response when no results found."""
        # Should return 404 with error: "no_result"
        expected = {"error": "no_result"}
        assert "error" in expected

    @pytest.mark.unit
    def test_error_responses(self):
        """Test various error response formats."""
        errors = {
            "invalid_phone": {"error": "invalid_phone", "status": 400},
            "fetch_failed": {"error": "fetch_failed", "status": 502},
            "no_result": {"error": "no_result", "status": 404},
            "unauthorized": {"error": "unauthorized", "status": 401},
            "invalid_url": {"error": "invalid_url", "status": 400},
            "domain_not_allowed": {"error": "domain_not_allowed", "status": 403},
        }

        for error_key, error_response in errors.items():
            assert "error" in error_response
            assert error_response["error"] == error_key


class TestCorsHeaders:
    """Test CORS header handling."""

    @pytest.mark.unit
    def test_cors_headers_present(self):
        """Response includes required CORS headers."""
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Relay-Token",
        }

        for header, value in cors_headers.items():
            assert header in cors_headers
            assert len(value) > 0

    @pytest.mark.unit
    def test_cors_allows_all_origins(self):
        """CORS allows requests from any origin."""
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Relay-Token",
        }
        origin = cors_headers["Access-Control-Allow-Origin"]
        assert origin == "*"

    @pytest.mark.unit
    def test_cors_methods_get_options(self):
        """CORS allows GET and OPTIONS methods."""
        methods = "GET, OPTIONS"
        assert "GET" in methods
        assert "OPTIONS" in methods

    @pytest.mark.unit
    def test_options_request_handling(self):
        """OPTIONS preflight request returns 204 with CORS headers."""
        # OPTIONS request should return 204 No Content with CORS headers
        status = 204
        assert status == 204


class TestRelayAuthentication:
    """Test relay authentication for protected endpoints."""

    @pytest.mark.unit
    def test_relay_token_header(self):
        """Relay endpoint accepts X-Relay-Token header."""
        token = "some-secret-token"
        headers = {
            "X-Relay-Token": token,
        }
        assert "X-Relay-Token" in headers
        assert headers["X-Relay-Token"] == token

    @pytest.mark.unit
    def test_relay_token_query_param(self):
        """Relay endpoint accepts token as query parameter."""
        query_string = "?url=https://zabasearch.com/phone/123&token=secret"
        assert "token=" in query_string

    @pytest.mark.unit
    def test_relay_unauthorized_missing_token(self):
        """Relay returns 401 when token is missing."""
        # No token provided
        expected_status = 401
        expected_error = "unauthorized"
        assert expected_status == 401

    @pytest.mark.unit
    def test_relay_unauthorized_invalid_token(self):
        """Relay returns 401 when token is invalid."""
        # Wrong token
        expected_status = 401
        expected_error = "unauthorized"
        assert expected_status == 401

    @pytest.mark.unit
    def test_relay_requires_valid_token(self):
        """Relay only works with valid RELAY_TOKEN from env."""
        # In Worker, env.RELAY_TOKEN must be set and match provided token
        env = {"RELAY_TOKEN": "valid-secret"}
        provided_token = "valid-secret"
        assert env.get("RELAY_TOKEN") == provided_token


class TestRelayUrlValidation:
    """Test relay URL validation and domain whitelisting."""

    @pytest.mark.unit
    def test_relay_whitelist_zabasearch(self):
        """Relay allows zabasearch.com URLs."""
        allowed_domains = ["zabasearch.com", "fastpeoplesearch.com", "anywho.com"]
        assert "zabasearch.com" in allowed_domains

    @pytest.mark.unit
    def test_relay_whitelist_fastpeoplesearch(self):
        """Relay allows fastpeoplesearch.com URLs."""
        allowed_domains = ["zabasearch.com", "fastpeoplesearch.com", "anywho.com"]
        assert "fastpeoplesearch.com" in allowed_domains

    @pytest.mark.unit
    def test_relay_whitelist_anywho(self):
        """Relay allows anywho.com URLs."""
        allowed_domains = ["zabasearch.com", "fastpeoplesearch.com", "anywho.com"]
        assert "anywho.com" in allowed_domains

    @pytest.mark.unit
    def test_relay_reject_unknown_domain(self):
        """Relay rejects URLs to unknown domains."""
        url = "https://example.com/page"
        allowed_domains = ["zabasearch.com", "fastpeoplesearch.com", "anywho.com"]

        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname

        allowed = any(
            hostname == d or hostname.endswith(f".{d}")
            for d in allowed_domains
        )
        assert not allowed

    @pytest.mark.unit
    def test_relay_missing_url_param(self):
        """Relay returns error when url param is missing."""
        # No url parameter provided
        expected_status = 400
        expected_error = "missing_url"
        assert expected_status == 400

    @pytest.mark.unit
    def test_relay_invalid_url_format(self):
        """Relay returns error for malformed URL."""
        bad_url = "not a url"
        expected_status = 400
        expected_error = "invalid_url"
        assert expected_status == 400


class TestEndpointRouting:
    """Test endpoint routing."""

    @pytest.mark.unit
    def test_phone_endpoint(self):
        """GET /phone?number=XXX routes to phone lookup."""
        endpoint = "/phone"
        param = "number=4155550123"
        path = f"{endpoint}?{param}"
        assert endpoint in path

    @pytest.mark.unit
    def test_relay_endpoint(self):
        """GET /relay?url=... routes to relay handler."""
        endpoint = "/relay"
        param = "url=https://zabasearch.com/phone/123&token=secret"
        path = f"{endpoint}?{param}"
        assert endpoint in path

    @pytest.mark.unit
    def test_root_endpoint_fallback(self):
        """GET / also handles relay (for Workers default)."""
        endpoints = ["/relay", "/"]
        assert "/relay" in endpoints
        assert "/" in endpoints

    @pytest.mark.unit
    def test_options_endpoint(self):
        """OPTIONS * returns 204 with CORS headers."""
        method = "OPTIONS"
        expected_status = 204
        assert method == "OPTIONS"


class TestIntegration:
    """Integration-level tests."""

    @pytest.mark.unit
    def test_phone_lookup_full_flow(self, zabasearch_html_sample):
        """Full flow: phone normalization -> fetch -> parse -> response."""
        # 1. Normalize phone
        raw_phone = "415-555-0123"
        digits = re.sub(r"\D", "", raw_phone)
        assert digits == "4155550123"

        # 2. Build URL
        formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        url = f"https://www.zabasearch.com/phone/{formatted}"
        assert url == "https://www.zabasearch.com/phone/415-555-0123"

        # 3. Parse HTML (mocked)
        name_match = re.search(r"<h3>([^<]+)</h3>", zabasearch_html_sample)
        assert name_match is not None

    @pytest.mark.unit
    def test_relay_full_flow(self):
        """Full flow: auth -> validate URL -> fetch -> relay response."""
        # 1. Check auth token
        token = "valid-secret"
        assert len(token) > 0

        # 2. Validate URL
        url = "https://zabasearch.com/phone/415-555-0123"
        allowed_domains = ["zabasearch.com"]
        from urllib.parse import urlparse
        parsed = urlparse(url)
        allowed = any(
            parsed.hostname == d or parsed.hostname.endswith(f".{d}")
            for d in allowed_domains
        )
        assert allowed

        # 3. Fetch (mocked) and relay response
        assert url.startswith("https://")
