"""
Data-quality tests for zaba_html_scraper against real captured HTML.

Zaba publishes full profiles directly on the search page, so one fetch yields
everything: aliases, relatives, phones with line type and carrier, emails, the
current address with county and coordinates, and past addresses. No other
broker supplies carrier or line type.

Two Zaba-specific traps are covered here:
  - it usually masks the email local part with literal x's ("xxxxx@aol.com"),
    which parses as a perfectly valid address
  - it 404s for an unknown person rather than serving an empty results page
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from zaba_html_scraper import ZabaHtmlScraper, ZabaHtmlScraperParams  # noqa: E402
from data_quality import (  # noqa: E402
    FULL_PHONE,
    assert_capped,
    assert_emails_complete,
    assert_street_address,
)

FIXTURES = Path(__file__).parent / "fixtures" / "zaba"

pytestmark = pytest.mark.unit


def load(name):
    return (FIXTURES / f"{name}.html").read_text()


@pytest.fixture(scope="module")
def scraper():
    return ZabaHtmlScraper(api_key="test-dummy")


@pytest.fixture(scope="module")
def oehring(scraper):
    profiles = scraper._extract_profiles_from_html(load("james_oehring_mo"))
    assert profiles, "expected a profile for James Oehring / Cameron MO"
    return profiles[0]


class TestSearchUrl:
    def test_path_based_url(self, scraper):
        url = scraper._build_search_url(
            ZabaHtmlScraperParams(firstName="James", lastName="Oehring", city="Cameron", state="MO")
        )
        assert url == "https://www.zabasearch.com/people/james-oehring/missouri/cameron"

    def test_multiword_city_is_hyphenated(self, scraper):
        url = scraper._build_search_url(
            ZabaHtmlScraperParams(firstName="Lucas", lastName="Clark", city="Kansas City", state="MO")
        )
        assert url.endswith("/lucas-clark/missouri/kansas-city")


class TestKnownProfile:
    def test_identity(self, oehring):
        assert oehring.fullName == "James Oehring"
        assert oehring.age == 37

    def test_stable_profile_id(self, oehring):
        # Zaba exposes a content hash on the card; useful for dedup across runs
        assert len(oehring.profileId) == 64

    def test_current_address(self, oehring):
        assert oehring.currentAddress["street"] == "413 Lovers LN"
        assert oehring.currentAddress["city"] == "Cameron"
        assert oehring.currentAddress["postalCode"] == "64429"
        assert_street_address(oehring.currentAddress["formatted"], "zaba oehring")

    def test_county_and_coordinates(self, oehring):
        # Neither is available from FPS, NPD or AnyWho
        assert oehring.currentAddress["county"] == "Dekalb"
        assert oehring.currentAddress["latitude"].startswith("39.")
        assert oehring.currentAddress["longitude"].startswith("-94.")

    def test_past_addresses(self, oehring):
        assert len(oehring.pastAddresses) == 2
        assert all(a["city"] == "Kansas City" for a in oehring.pastAddresses)

    def test_aliases(self, oehring):
        assert "james O oehring" in oehring.aliases

    def test_relatives(self, oehring):
        assert [r["name"] for r in oehring.relatives] == ["Rickilinda R Oehring"]

    def test_unmasked_email_is_kept(self, oehring):
        assert oehring.emailAddresses == ["rickioehring@yahoo.com"]


class TestPhoneEnrichment:
    """Line type and carrier are Zaba's distinguishing contribution."""

    def test_both_numbers_found(self, oehring):
        numbers = {p["number"] for p in oehring.phoneNumbers}
        assert numbers == {"(816) 225-8592", "(816) 632-2218"}

    def test_all_numbers_well_formed(self, oehring):
        for phone in oehring.phoneNumbers:
            assert FULL_PHONE.match(phone["number"]), phone

    def test_line_type_and_carrier(self, oehring):
        by_number = {p["number"]: p for p in oehring.phoneNumbers}
        assert by_number["(816) 225-8592"]["type"] == "Mobile"
        assert "AT&T" in by_number["(816) 225-8592"]["carrier"]
        assert by_number["(816) 632-2218"]["type"] == "LandLine".capitalize()

    def test_primary_flag(self, oehring):
        primary = [p for p in oehring.phoneNumbers if p.get("primary")]
        assert len(primary) == 1
        assert primary[0]["number"] == "(816) 225-8592"

    def test_first_reported_captured(self, oehring):
        by_number = {p["number"]: p for p in oehring.phoneNumbers}
        assert by_number["(816) 632-2218"]["firstReported"] == "December 12, 2005"

    def test_line_type_casing_normalised(self, scraper):
        # Zaba writes "Mobile" for one record and "mobile" for another
        for profile in scraper._extract_profiles_from_html(load("lucas_clark_mo")):
            for phone in profile.phoneNumbers:
                if phone["type"]:
                    assert phone["type"][0].isupper(), phone


class TestMaskedEmails:
    """
    Zaba substitutes a run of x's for the local part on most records. It parses
    as a valid address, so a format check alone would store "xxxxx@aol.com".
    """

    def test_masked_emails_dropped(self, scraper):
        for name in ("lucas_clark_mo", "claire_inman_ks"):
            for profile in scraper._extract_profiles_from_html(load(name)):
                for email in profile.emailAddresses:
                    local = email.split("@")[0]
                    assert set(local.lower()) != {"x"}, f"masked email stored: {email}"

    def test_real_emails_still_pass(self, scraper):
        emails = scraper._extract_profiles_from_html(load("james_oehring_mo"))[0].emailAddresses
        assert emails == ["rickioehring@yahoo.com"]


class TestMultipleResults:
    def test_extracts_each_person(self, scraper):
        profiles = scraper._extract_profiles_from_html(load("lucas_clark_mo"))
        assert len(profiles) == 2
        assert {p.age for p in profiles} == {34, 30}

    def test_profile_ids_are_distinct(self, scraper):
        profiles = scraper._extract_profiles_from_html(load("lucas_clark_mo"))
        assert len({p.profileId for p in profiles}) == len(profiles)

    def test_fields_capped(self, scraper):
        for profile in scraper._extract_profiles_from_html(load("lucas_clark_mo")):
            assert len(profile.phoneNumbers) <= 20
            assert len(profile.emailAddresses) <= 20
            assert len(profile.aliases) <= 20


class TestSummaryProjection:
    """Zaba has no summary page, so summary rows are flattened full profiles."""

    def test_summary_mirrors_profile(self, scraper, oehring):
        summary = scraper._to_summary(oehring, 0)
        assert summary.fullName == "James Oehring"
        assert summary.age == 37
        assert "413 Lovers LN" in summary.address
        assert "(816) 632-2218" in summary.phone
        assert summary.relatives == "Rickilinda R Oehring"

    def test_summary_values_are_complete(self, scraper, oehring):
        summary = scraper._to_summary(oehring, 0)
        assert_emails_complete(summary.email, "zaba oehring")
        for field in ("phone", "email", "aliases", "relatives"):
            assert_capped(getattr(summary, field), 5, f"zaba.{field}")


class TestNoResults:
    """Zaba 404s for an unknown person instead of serving an empty page."""

    def test_404_is_no_results_not_failure(self, scraper, monkeypatch):
        class Boom:
            def web_scrape_html(self, url):
                raise RuntimeError(
                    "Error code: 404 - {'message': 'Target page returned a 404', "
                    "'error_code': 'NOT_FOUND'}"
                )

        monkeypatch.setattr(scraper, "client", type("C", (), {"web": Boom()})())
        output = scraper.run(
            dict(firstName="Zqxjv", lastName="Wkltmr", city="Cameron", state="MO")
        )
        assert output.status == "no_results"
        assert output.error is None
        assert output.profiles == []

    def test_genuine_failure_is_reported(self, scraper, monkeypatch):
        class Boom:
            def web_scrape_html(self, url):
                raise RuntimeError("Error code: 500 - upstream exploded")

        monkeypatch.setattr(scraper, "client", type("C", (), {"web": Boom()})())
        output = scraper.run(
            dict(firstName="James", lastName="Oehring", city="Cameron", state="MO")
        )
        assert output.status == "failed"
        assert "500" in output.error
