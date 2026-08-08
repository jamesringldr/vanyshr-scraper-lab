"""
Unit tests for NPD scraper (workers/npd/npd_scraper.py).

All network calls mocked — fixtures under tests/fixtures/npd/.
"""

import sys
from pathlib import Path

import pytest

workers_path = Path(__file__).parent.parent / "workers"
sys.path.insert(0, str(workers_path / "npd"))

from npd_scraper import (  # noqa: E402
    build_url,
    is_blocked,
    parse_profiles,
    slug,
)

FIXTURES = Path(__file__).parent / "fixtures" / "npd"


@pytest.fixture
def mo_list_html():
    return (FIXTURES / "james_oehring_mo.html").read_text(encoding="utf-8")


@pytest.fixture
def detail_html():
    return (FIXTURES / "james_oehring_detail.html").read_text(encoding="utf-8")


@pytest.fixture
def blocked_html():
    return (FIXTURES / "cf_blocked.html").read_text(encoding="utf-8")


@pytest.fixture
def no_results_html():
    return (FIXTURES / "no_results.html").read_text(encoding="utf-8")


class TestSlug:
    @pytest.mark.unit
    def test_slug_basic(self):
        assert slug("James") == "james"
        assert slug("San Francisco") == "san-francisco"

    @pytest.mark.unit
    def test_slug_special(self):
        assert slug("O'Brien") == "obrien"


class TestBuildUrl:
    @pytest.mark.unit
    def test_name_only(self):
        assert build_url("James", "Oehring") == (
            "https://nationalpublicdata.com/people/o/james-oehring/"
        )

    @pytest.mark.unit
    def test_with_state(self):
        assert build_url("James", "Oehring", state="MO") == (
            "https://nationalpublicdata.com/people/o/james-oehring/mo/"
        )

    @pytest.mark.unit
    def test_with_city_state(self):
        assert build_url("James", "Oehring", "Cameron", "MO") == (
            "https://nationalpublicdata.com/people/o/james-oehring/mo/cameron/"
        )

    @pytest.mark.unit
    def test_letter_from_last(self):
        assert "/people/s/john-smith/" in build_url("John", "Smith")


class TestIsBlocked:
    @pytest.mark.unit
    def test_blocked_status(self):
        assert is_blocked(403, "<html>ok long " + ("x" * 9000) + "</html>")
        assert is_blocked(429, "<html></html>")

    @pytest.mark.unit
    def test_cf_challenge_title(self, blocked_html):
        assert is_blocked(200, blocked_html)

    @pytest.mark.unit
    def test_real_page_not_blocked(self, mo_list_html):
        assert not is_blocked(200, mo_list_html)


class TestParseProfiles:
    @pytest.mark.unit
    def test_parse_mo_list(self, mo_list_html):
        profiles = parse_profiles(mo_list_html)
        assert len(profiles) >= 1
        p = profiles[0]
        assert "Oehring" in p["name"]
        assert p["source"] == "NPD"
        assert p["detail_link"] and "james-oehring" in p["detail_link"]
        assert p["age"] is not None
        assert p["phones"]
        assert p["addresses"]
        assert any(a.get("city") == "Cameron" for a in p["addresses"])

    @pytest.mark.unit
    def test_parse_detail(self, detail_html):
        profiles = parse_profiles(detail_html)
        assert len(profiles) == 1
        p = profiles[0]
        assert p["name"] == "James Oehring"
        assert p["birth_year"] == "1963"
        assert p["city_state"] == "Cameron, MO"
        assert any("(816)" in ph["number"] for ph in p["phones"])
        assert p["emails"]
        assert p["relatives"]
        assert p["id"] and p["id"].startswith("pd")

    @pytest.mark.unit
    def test_no_results(self, no_results_html):
        assert parse_profiles(no_results_html) == []
