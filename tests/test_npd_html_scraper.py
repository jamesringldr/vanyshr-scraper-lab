"""
Data-quality tests for npd_html_scraper against real captured HTML.

NPD is the richest Phase 1 source but publishes almost nothing in the visible
result card: phones, emails, the street address and relatives live only in the
embedded JSON-LD Person block. A parser that reads the rendered card alone
returns a result that looks fine (name + age + "Cameron, MO") while silently
dropping every contact field the page actually carries.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from npd_html_scraper import NPDHtmlScraper, NPDHtmlScraperParams  # noqa: E402
from data_quality import (  # noqa: E402
    assert_emails_complete,
    assert_phones_complete,
    assert_street_address,
)

FIXTURES = Path(__file__).parent / "fixtures" / "npd"

pytestmark = pytest.mark.unit


def load(name):
    return (FIXTURES / f"{name}.html").read_text()


@pytest.fixture(scope="module")
def scraper():
    return NPDHtmlScraper(api_key="test-dummy")


@pytest.fixture(scope="module")
def oehring(scraper):
    results = scraper._extract_summary_from_html(load("james_oehring_mo"))
    assert results, "expected a result for James Oehring / Cameron MO"
    return results[0]


class TestSearchUrl:
    def test_url_format(self, scraper):
        url = scraper._build_search_url(
            NPDHtmlScraperParams(firstName="James", lastName="Oehring", city="Cameron", state="MO")
        )
        assert url == "https://nationalpublicdata.com/people/o/james-oehring/mo/cameron/"


class TestVisibleCard:
    def test_name(self, oehring):
        assert oehring.fullName == "James Oehring"

    def test_age(self, oehring):
        assert oehring.ageRange == "62"


class TestJsonLdFields:
    """These exist only in the JSON-LD block, never in the rendered card."""

    def test_phones_extracted_and_formatted(self, oehring):
        # JSON-LD carries bare digits ("8166322218"); normalise for consistency
        # with the other brokers so downstream dedup compares like with like.
        assert "(816) 632-2218" in oehring.phonePreview
        assert "(816) 225-8592" in oehring.phonePreview

    def test_phones_complete(self, oehring):
        assert_phones_complete(oehring.phonePreview, "npd oehring")

    def test_emails_extracted(self, oehring):
        assert "ja_studly@hotmail.com" in oehring.email

    def test_emails_complete(self, oehring):
        assert_emails_complete(oehring.email, "npd oehring")

    def test_street_address_extracted(self, oehring):
        assert "413 Lovers Ln" in oehring.addressPreview
        assert_street_address(oehring.addressPreview, "npd oehring")

    def test_relatives_extracted(self, oehring):
        assert "Rickilinda Oehring" in oehring.relatives


class TestNoResults:
    def test_empty_page_yields_nothing(self, scraper):
        assert scraper._extract_summary_from_html(load("no_results")) == []

    def test_cloudflare_block_yields_nothing(self, scraper):
        assert scraper._extract_summary_from_html(load("cf_blocked")) == []
