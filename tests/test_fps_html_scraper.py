"""
Data-quality tests for fps_html_scraper against real captured HTML.

FPS differs from AnyWho: nothing is blurred, but the search page shows only a
coarse "Cameron, MO" as the link text while the full street address is carried
in the anchor's title attribute. Relatives are likewise present as links under
an <h4>Relatives:</h4> heading.

Phones and personal emails are genuinely absent from the FPS summary page --
they appear only on the full profile page (Phase 2). Tests assert that absence
deliberately, so nobody hunts for a bug that isn't there.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fps_html_scraper import FPSHtmlScraper  # noqa: E402
from data_quality import (  # noqa: E402
    assert_emails_complete,
    assert_phones_complete,
    assert_street_address,
    split_multi,
)

FIXTURES = Path(__file__).parent / "fixtures" / "fps"

pytestmark = pytest.mark.unit


def load(name):
    return (FIXTURES / f"{name}.html").read_text()


@pytest.fixture(scope="module")
def scraper():
    return FPSHtmlScraper(api_key="test-dummy")


@pytest.fixture(scope="module")
def oehring(scraper):
    results = scraper._extract_summary_from_html(load("james_oehring_mo"))
    assert results, "expected at least one result for James Oehring / Cameron MO"
    return results[0]


class TestKnownProfile:
    def test_name(self, oehring):
        assert oehring.fullName == "James Oehring"

    def test_age(self, oehring):
        assert oehring.age == 61

    def test_full_street_address_from_title_attribute(self, oehring):
        # Link text is only "Cameron, MO"; the street lives in the title attr
        # (href=/address/413-lovers-ln_cameron-mo-64429)
        assert "413 Lovers Ln" in oehring.address, (
            f"street address not recovered, got {oehring.address!r}"
        )
        assert_street_address(oehring.address, "oehring")

    def test_relatives_extracted(self, oehring):
        assert "Rickilinda Oehring" in oehring.relatives, (
            f"relatives not extracted, got {oehring.relatives!r}"
        )


class TestSummaryPageLimits:
    """Document what the FPS summary page genuinely does not carry."""

    def test_no_phone_on_summary_page(self, oehring):
        # Confirmed absent from the captured HTML; comes from the full profile.
        assert oehring.phone == ""

    def test_no_personal_email_on_summary_page(self, oehring):
        assert oehring.email == ""


class TestMultiResultPage:
    def test_extracts_multiple_people(self, scraper):
        results = scraper._extract_summary_from_html(load("lucas_clark_mo"))
        assert len(results) >= 2, f"expected several matches, got {len(results)}"

    def test_every_result_named_and_aged(self, scraper):
        for r in scraper._extract_summary_from_html(load("lucas_clark_mo")):
            assert r.fullName and len(r.fullName.split()) >= 2
            assert r.age is None or 0 < r.age < 120

    def test_extracted_values_are_complete(self, scraper):
        for name in ("lucas_clark_mo", "chris_ocker_mo"):
            for r in scraper._extract_summary_from_html(load(name)):
                assert_phones_complete(r.phone, r.fullName)
                assert_emails_complete(r.email, r.fullName)
