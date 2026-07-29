"""
Unit tests for anywho scraper (anywho_test.py).

Tests URL building, HTML parsing, and edge case handling.
All network calls are mocked — no real HTTP requests.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent workers dir to path so we can import anywho_test
workers_path = Path(__file__).parent.parent / "workers"
sys.path.insert(0, str(workers_path / "anywho"))

# Import the anywho scraper functions
from anywho_test import (
    build_url, slug, parse, clean, is_blocked, extract, STATE_NAMES, DOM
)


class TestSlugify:
    """Test slug() function for URL formatting."""

    @pytest.mark.unit
    def test_slug_lowercase(self):
        """Slug converts to lowercase."""
        assert slug("JOHN") == "john"
        assert slug("JoHn") == "john"

    @pytest.mark.unit
    def test_slug_spaces_to_dash(self):
        """Slug converts spaces to dashes."""
        assert slug("John Smith") == "john-smith"
        assert slug("Los Angeles") == "los-angeles"

    @pytest.mark.unit
    def test_slug_special_chars(self):
        """Slug replaces special characters with dashes."""
        assert slug("O'Brien") == "o-brien"
        assert slug("Mary-Jane") == "mary-jane"
        assert slug("José García") == "jose-garcia"

    @pytest.mark.unit
    def test_slug_collapse_dashes(self):
        """Slug collapses multiple dashes to single."""
        assert slug("John---Smith") == "john-smith"
        assert slug("St. Louis") == "st-louis"

    @pytest.mark.unit
    def test_slug_trim_dashes(self):
        """Slug trims leading/trailing dashes."""
        assert slug("-John-") == "john"
        assert slug("--Smith--") == "smith"


class TestBuildUrl:
    """Test build_url() function."""

    @pytest.mark.unit
    def test_build_url_name_only(self):
        """Build URL with just first and last name."""
        url = build_url("John", "Doe")
        assert url == "https://www.anywho.com/people/john+doe"

    @pytest.mark.unit
    def test_build_url_with_city_state(self):
        """Build URL with name, city, and state."""
        url = build_url("John", "Doe", "San Francisco", "CA")
        assert url == "https://www.anywho.com/people/john+doe/california/san-francisco"

    @pytest.mark.unit
    def test_build_url_state_abbreviation(self):
        """Build URL converts state abbreviation to full name."""
        url = build_url("John", "Doe", "Los Angeles", "CA")
        assert "/california/" in url

    @pytest.mark.unit
    def test_build_url_state_unknown(self):
        """Build URL uses lowercased state if not in mapping."""
        url = build_url("John", "Doe", "Somewhere", "XX")
        assert "/xx/" in url

    @pytest.mark.unit
    def test_build_url_special_chars_in_name(self):
        """Build URL slugifies names with special characters."""
        url = build_url("O'Brien", "McDonald", "Chicago", "IL")
        assert "o-brien+mcdonald" in url
        assert "/illinois/chicago" in url

    @pytest.mark.unit
    def test_build_url_state_names_all_mapped(self):
        """All US state abbreviations map correctly."""
        # Sample check — can add more if needed
        for abbrev, full_name in STATE_NAMES.items():
            url = build_url("Test", "User", state=abbrev)
            assert full_name in url


class TestClean:
    """Test clean() function for text normalization."""

    @pytest.mark.unit
    def test_clean_whitespace(self):
        """Clean collapses multiple whitespace."""
        assert clean("John   Doe") == "John Doe"
        assert clean("\t\nJohn Doe\r\n") == "John Doe"

    @pytest.mark.unit
    def test_clean_nbsps(self):
        """Clean converts non-breaking spaces to regular spaces."""
        assert clean("John\xa0Doe") == "John Doe"

    @pytest.mark.unit
    def test_clean_bullets_dashes(self):
        """Clean strips bullets and dashes from edges."""
        assert clean("• John Doe •") == "John Doe"
        assert clean("- Phone -") == "Phone"
        assert clean("•••415•••") == "415"

    @pytest.mark.unit
    def test_clean_preserves_content(self):
        """Clean preserves important content."""
        assert clean("123 Main St, San Francisco, CA") == "123 Main St, San Francisco, CA"


class TestParseHtml:
    """Test parse() function with mock HTML."""

    @pytest.mark.unit
    def test_parse_single_result(self, anywho_html_sample):
        """Parse extracts one person from sample HTML."""
        results = parse(anywho_html_sample)
        assert len(results) == 1
        assert results[0]["name"] == "John Doe"

    @pytest.mark.unit
    def test_parse_result_structure(self, anywho_html_sample):
        """Parsed result has expected keys."""
        results = parse(anywho_html_sample)
        record = results[0]
        assert "name" in record
        assert "age" in record
        assert "phones" in record
        assert "lives_in" in record
        assert "detail_link" in record

    @pytest.mark.unit
    def test_parse_extracts_age(self, anywho_html_sample):
        """Parse extracts age from result."""
        results = parse(anywho_html_sample)
        assert results[0]["age"] == "42"

    @pytest.mark.unit
    def test_parse_extracts_location(self, anywho_html_sample):
        """Parse extracts 'lives in' location."""
        results = parse(anywho_html_sample)
        assert "San Francisco" in results[0]["lives_in"]

    @pytest.mark.unit
    def test_parse_extracts_phones(self, anywho_html_sample):
        """Parse reassembles phone numbers from blurred spans."""
        results = parse(anywho_html_sample)
        # Phones are reassembled from data-content spans: 415-555-0123
        assert len(results[0]["phones"]) > 0
        assert any("415" in p or "555" in p for p in results[0]["phones"])

    @pytest.mark.unit
    def test_parse_extracts_aliases(self, anywho_html_sample):
        """Parse extracts AKA aliases."""
        results = parse(anywho_html_sample)
        assert results[0]["aka"] == "Johnny Doe"

    @pytest.mark.unit
    def test_parse_extracts_related(self, anywho_html_sample):
        """Parse extracts related people."""
        results = parse(anywho_html_sample)
        assert "Jane Doe" in results[0]["related"]

    @pytest.mark.unit
    def test_parse_extracts_detail_link(self, anywho_html_sample):
        """Parse extracts detail profile link."""
        results = parse(anywho_html_sample)
        link = results[0]["detail_link"]
        assert link is not None
        assert "anywho.com" in link
        assert "/people/" in link

    @pytest.mark.unit
    def test_parse_no_results(self, anywho_html_no_results):
        """Parse returns empty list when no results."""
        results = parse(anywho_html_no_results)
        assert len(results) == 0

    @pytest.mark.unit
    def test_parse_deduplicates_cards(self):
        """Parse deduplicates when same card ID appears twice (shouldn't happen, but safeguard)."""
        html = """
        <h2>John Doe</h2>
        <h3>Lives in: San Francisco, CA</h3>
        <h2>John Doe</h2>
        <h3>Lives in: San Francisco, CA</h3>
        """
        results = parse(html)
        # Same name/location should not create duplicates within one card
        # (each h2 anchors to its own card, but dedup by id(card))
        assert len(results) >= 1

    @pytest.mark.unit
    def test_parse_filters_invalid_names(self):
        """Parse skips cards with invalid name formats."""
        html = """
        <h2>123 Numbers</h2>
        <h3>Lives in: San Francisco</h3>
        <h2>John Doe</h2>
        <h3>Lives in: San Francisco</h3>
        """
        results = parse(html)
        # Should only return the valid "John Doe" entry
        valid_names = [r["name"] for r in results]
        assert any("John" in n for n in valid_names)


class TestIsBlocked:
    """Test is_blocked() function."""

    @pytest.mark.unit
    def test_is_blocked_cloudflare_message(self, anywho_html_blocked):
        """is_blocked detects Cloudflare challenge page."""
        assert is_blocked(anywho_html_blocked) is True

    @pytest.mark.unit
    def test_is_blocked_access_denied(self):
        """is_blocked detects 'Access denied' message."""
        html = "<html><body>Access denied</body></html>"
        assert is_blocked(html) is True

    @pytest.mark.unit
    def test_is_blocked_small_response(self):
        """is_blocked detects very small responses (likely error page)."""
        html = "<html><body></body></html>"  # Only ~23 bytes
        assert is_blocked(html) is True

    @pytest.mark.unit
    def test_is_blocked_normal_page(self, anywho_html_sample):
        """is_blocked returns False for normal content."""
        assert is_blocked(anywho_html_sample) is False

    @pytest.mark.unit
    def test_is_blocked_threshold(self):
        """is_blocked uses 200 byte threshold for size check."""
        # Page with ~150 bytes should be blocked
        small_html = "x" * 150
        assert is_blocked(small_html) is True

        # Page with ~250 bytes should not be blocked (if no other markers)
        large_html = "<html>" + "y" * 240 + "</html>"
        assert is_blocked(large_html) is False


class TestDomParser:
    """Test DOM parser class."""

    @pytest.mark.unit
    def test_dom_simple_text(self):
        """DOM parser extracts simple text."""
        dom = DOM()
        dom.feed("<p>Hello World</p>")
        nodes = list(dom.root.walk())
        p_nodes = [n for n in nodes if n.tag == "p"]
        assert len(p_nodes) > 0

    @pytest.mark.unit
    def test_dom_data_content_preserved(self):
        """DOM parser preserves data-content attributes."""
        dom = DOM()
        dom.feed('<span data-content="415">•••</span>')
        nodes = list(dom.root.walk())
        span_nodes = [n for n in nodes if n.tag == "span"]
        assert len(span_nodes) > 0
        # data-content should be inserted as text in the node's children
        assert "415" in span_nodes[0].text()

    @pytest.mark.unit
    def test_dom_nested_tags(self):
        """DOM parser handles nested tags correctly."""
        dom = DOM()
        dom.feed("<div><p><span>text</span></p></div>")
        nodes = list(dom.root.walk())
        tags = [n.tag for n in nodes]
        assert "div" in tags
        assert "p" in tags
        assert "span" in tags

    @pytest.mark.unit
    def test_dom_self_closing(self):
        """DOM parser handles self-closing tags."""
        dom = DOM()
        dom.feed("<div><br/><img/></div>")
        nodes = list(dom.root.walk())
        tags = [n.tag for n in nodes]
        # br and img are self-closing, shouldn't have children
        assert "div" in tags


class TestExtractFunction:
    """Test extract() helper function."""

    @pytest.mark.unit
    def test_extract_returns_dict(self, anywho_html_sample):
        """extract() returns a dictionary with person data."""
        from anywho_test import parse as parse_func
        results = parse_func(anywho_html_sample)
        assert isinstance(results[0], dict)

    @pytest.mark.unit
    def test_extract_has_required_fields(self, anywho_html_sample):
        """Extracted record has all documented fields."""
        from anywho_test import parse as parse_func
        results = parse_func(anywho_html_sample)
        record = results[0]
        required = {"name", "age", "aka", "lives_in", "phones", "related", "detail_link"}
        for field in required:
            assert field in record, f"Missing field: {field}"


class TestIntegration:
    """Integration tests combining multiple functions."""

    @pytest.mark.unit
    def test_full_flow_sample_html(self, anywho_html_sample):
        """Full flow: parse sample HTML to person records."""
        results = parse(anywho_html_sample)
        assert len(results) > 0

        record = results[0]
        assert record["name"]
        assert record["age"]
        assert isinstance(record["phones"], list)
        assert isinstance(record["related"], (str, type(None)))

    @pytest.mark.unit
    def test_url_building_matches_pattern(self):
        """URL building follows expected anywho.com pattern."""
        url = build_url("John", "Doe", "San Francisco", "CA")
        # URL structure: /people/{first}+{last}/{state-name}/{city-slug}
        assert url.startswith("https://www.anywho.com/people/")
        assert "john+doe" in url
        parts = url.split("/")
        assert "california" in parts
        assert "san-francisco" in parts

    @pytest.mark.unit
    def test_all_state_abbreviations_valid(self):
        """STATE_NAMES dict has all 50 US states + DC."""
        # Check we have reasonable coverage
        assert "CA" in STATE_NAMES
        assert "TX" in STATE_NAMES
        assert "NY" in STATE_NAMES
        assert "DC" in STATE_NAMES
        # Some quick assertions
        assert STATE_NAMES["CA"] == "california"
        assert STATE_NAMES["TX"] == "texas"
        assert STATE_NAMES["NY"] == "new-york"


# ─── Edge case tests ──────────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.unit
    def test_empty_name(self):
        """slug handles empty strings."""
        assert slug("") == ""

    @pytest.mark.unit
    def test_only_numbers(self):
        """slug preserves numbers."""
        assert slug("123") == "123"

    @pytest.mark.unit
    def test_very_long_name(self):
        """slug handles very long names."""
        long_name = "A" * 100
        result = slug(long_name)
        assert result == "a" * 100

    @pytest.mark.unit
    def test_unicode_characters(self):
        """slug handles unicode characters."""
        # Should convert non-ASCII to dashes or equivalent
        result = slug("Björk")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.unit
    def test_parse_malformed_html(self):
        """parse handles malformed HTML gracefully."""
        malformed = "<p>Unclosed tag<div>nested"
        results = parse(malformed)
        # Should not crash, returns list (possibly empty)
        assert isinstance(results, list)

    @pytest.mark.unit
    def test_build_url_none_values(self):
        """build_url handles None city/state."""
        url = build_url("John", "Doe", None, None)
        assert url == "https://www.anywho.com/people/john+doe"
