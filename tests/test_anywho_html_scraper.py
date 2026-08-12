"""
Data-quality tests for anywho_html_scraper against real captured HTML.

AnyWho serves sensitive values blurred: the visible text holds the leading
fragment and the remainder lives in a `data-content` attribute on an empty
nested span, rendered via CSS `before:content-[attr(data-content)]`. Any parser
that reads visible text only produces plausible-looking half-values.

Fixtures are real pages captured by tests/capture_fixtures.py. No network here.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from anywho_html_scraper import AnyWhoHtmlScraper  # noqa: E402
from data_quality import (  # noqa: E402
    assert_capped,
    assert_emails_complete,
    assert_no_ui_artifacts,
    assert_phones_complete,
    assert_street_address,
    assert_summary_quality,
    split_multi,
)

FIXTURES = Path(__file__).parent / "fixtures" / "anywho"

pytestmark = pytest.mark.unit


def load(name):
    return (FIXTURES / f"{name}.html").read_text()


@pytest.fixture(scope="module")
def scraper():
    return AnyWhoHtmlScraper(api_key="test-dummy")


@pytest.fixture(scope="module")
def oehring(scraper):
    results = scraper._extract_summary_from_html(load("james_oehring_mo"))
    assert results, "expected at least one result for James Oehring / Cameron MO"
    return results[0]


class TestDataContentReconstruction:
    """The blurred fragments must survive into the extracted values."""

    def test_phone_keeps_blurred_last_four(self, oehring):
        # data-content="2218" completes the visible "(816) 632-"
        assert "(816) 632-2218" in oehring.phone

    def test_phone_is_not_truncated(self, oehring):
        assert_phones_complete(oehring.phone, "oehring")

    def test_email_keeps_blurred_local_part(self, oehring):
        # data-content="astudly" completes the visible "j"
        assert "jastudly@hotmail.com" in oehring.email

    def test_all_emails_complete(self, oehring):
        assert_emails_complete(oehring.email, "oehring")

    def test_address_keeps_blurred_street_number(self, oehring):
        # data-content="1225" and "502" complete "Union Ave, Apt , Kansas City, MO"
        assert_street_address(oehring.address, "oehring")
        assert "1225" in oehring.address

    def test_age_is_extracted(self, oehring):
        # The age span also contains an <svg>, which defeats a bs4 `string=` match
        assert oehring.ageRange, "age not extracted"
        assert oehring.ageRange.isdigit() and 0 < int(oehring.ageRange) < 120


class TestKnownProfile:
    """Spot-check against a person whose real details are known."""

    def test_name(self, oehring):
        assert oehring.fullName == "James A Oehring"

    def test_alias(self, oehring):
        assert "James Allen Oehring Jr." in oehring.aliases

    def test_relative(self, oehring):
        assert "Rickilinda Oehring" in oehring.relatives


class TestMultiResultPage:
    def test_extracts_multiple_people(self, scraper):
        results = scraper._extract_summary_from_html(load("chris_rodgers_ks"))
        assert len(results) >= 2, f"expected several matches, got {len(results)}"

    def test_every_result_is_complete(self, scraper):
        results = scraper._extract_summary_from_html(load("chris_rodgers_ks"))
        for r in results:
            # Not every person lists a phone or email, but whatever is
            # extracted must be whole.
            assert_summary_quality(r, r.fullName, expect_phone=False, expect_email=False)

    def test_no_result_is_a_page_furniture_heading(self, scraper):
        results = scraper._extract_summary_from_html(load("chris_rodgers_ks"))
        junk = {"Filter by State", "Filter by Age", "Frequently Asked Questions"}
        assert not [r for r in results if r.fullName in junk]


class TestListHygiene:
    """
    AnyWho truncates long lists with a "show more" affordance ("+ 2 more"),
    separated by the same bullet as the real entries. Observed in a live run as
    a relative literally named "+ 1 more".
    """

    def test_show_more_not_stored_as_a_relative(self, scraper):
        for r in scraper._extract_summary_from_html(load("chris_rodgers_ks")):
            assert_no_ui_artifacts(r.relatives, f"{r.fullName}.relatives")
            assert_no_ui_artifacts(r.aliases, f"{r.fullName}.aliases")

    @pytest.mark.parametrize("field", ["phone", "email", "aliases", "relatives"])
    def test_fields_capped_at_five(self, scraper, field):
        for r in scraper._extract_summary_from_html(load("chris_rodgers_ks")):
            assert_capped(getattr(r, field), 5, f"{r.fullName}.{field}")

    def test_join_section_drops_affordance_and_caps(self, scraper):
        joined = scraper._join_section(
            ["Ann Smith", "+ 2 more", "Bo Lee", "more", "Cy Fox", "Di Ray", "Ed Poe", "Fay Ito"]
        )
        assert "more" not in joined
        assert len(joined.split(",")) == 5

    def test_join_section_deduplicates(self, scraper):
        assert scraper._join_section(["Ann Smith", "Ann Smith"]) == "Ann Smith"


class TestNoResults:
    def test_absent_person_yields_nothing(self, scraper):
        assert scraper._extract_summary_from_html(load("no_results")) == []


class TestReconstructionUnit:
    """Direct unit coverage of the reconstruction helper."""

    def _frag(self, scraper, html):
        from bs4 import BeautifulSoup

        return scraper._reconstruct_with_data_content(
            BeautifulSoup(html, "html.parser").find("div")
        )

    def test_recovers_nested_data_content(self, scraper):
        # The real shape: div > span > span[data-content], the inner span empty
        html = (
            '<div><span><span>(816) 632-</span>'
            '<span class="blur-sm" data-content="2218"></span></span></div>'
        )
        assert "2218" in self._frag(scraper, html)

    def test_recovers_data_content_below_a_div(self, scraper):
        html = '<div><div><span data-content="1225"></span><span> Union Ave</span></div></div>'
        out = self._frag(scraper, html)
        assert "1225" in out and "Union Ave" in out

    def test_plain_text_is_unchanged(self, scraper):
        assert "Cameron, MO" in self._frag(scraper, "<div><span>Cameron, MO</span></div>")
