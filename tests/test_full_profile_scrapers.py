"""
Data-quality tests for the three full-profile scrapers.

These previously ran regexes across the whole page, which invented values that
looked entirely real once stored:

  FPS     (369) 730-5023  -- digits from the profile URL id G3697305023830937972
  AnyWho  (626) 555-5555  -- a form's placeholder attribute
  AnyWho  linkedin@2x.a7ffbfd3.png -- a sprite filename matching an email regex
  NPD     (611) 503-8382  -- a digit run appearing nowhere as a phone number

A truncated value is visibly wrong; a fabricated phone number is not. So the
central assertion here is that every extracted value can be corroborated
against the page, and that the specific fabrications above never reappear.

FPS and NPD now read their schema.org Person block; AnyWho has none and is
parsed from its rendered cards.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from anywho_full_profile_scraper import AnyWhoFullProfileScraper  # noqa: E402
from fps_full_profile_scraper import FPSFullProfileScraper  # noqa: E402
from npd_full_profile_scraper import NPDFullProfileScraper  # noqa: E402
from data_quality import FULL_PHONE, assert_street_address  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.unit

# Values the old implementations invented; none may ever come back
FABRICATED = {
    "(369) 730-5023", "(018) 340-6007", "(626) 555-5555",
    "(611) 503-8382", "(414) 640-2143", "(701) 104-6249",
}


def load(broker, name):
    return (FIXTURES / broker / f"{name}_profile.html").read_text()


@pytest.fixture(scope="module")
def fps():
    return FPSFullProfileScraper(api_key="test-dummy")._parse_profile_html(
        load("fps", "james_oehring_mo"), "pid"
    )


@pytest.fixture(scope="module")
def npd():
    return NPDFullProfileScraper(api_key="test-dummy")._parse_profile_html(
        load("npd", "james_oehring_mo"), "pid"
    )


@pytest.fixture(scope="module")
def anywho():
    return AnyWhoFullProfileScraper(api_key="test-dummy")._parse_profile_html(
        load("anywho", "james_oehring_mo"), "pid"
    )


class TestNoFabrication:
    """No value may appear that isn't on the page."""

    def test_all_parsers_return_a_profile(self, fps, npd, anywho):
        assert fps and npd and anywho

    @pytest.mark.parametrize("broker", ["fps", "npd", "anywho"])
    def test_no_known_fabricated_phone(self, broker, fps, npd, anywho):
        profile = {"fps": fps, "npd": npd, "anywho": anywho}[broker]
        numbers = {p["number"] for p in profile.phoneNumbers}
        assert not (numbers & FABRICATED), f"{broker} reintroduced a fabricated number"

    @pytest.mark.parametrize("broker", ["fps", "npd", "anywho"])
    def test_every_phone_is_well_formed(self, broker, fps, npd, anywho):
        profile = {"fps": fps, "npd": npd, "anywho": anywho}[broker]
        for phone in profile.phoneNumbers:
            assert FULL_PHONE.match(phone["number"]), f"{broker}: {phone}"

    @pytest.mark.parametrize("broker", ["fps", "npd", "anywho"])
    def test_phones_appear_in_the_source(self, broker, fps, npd, anywho):
        """
        The strongest check: every number must be traceable to the page.

        AnyWho blurs its numbers across data-content attributes, so the digits
        never appear literally in the markup -- that page is checked against
        its reconstructed text instead.
        """
        profile = {"fps": fps, "npd": npd, "anywho": anywho}[broker]
        html = load(broker, "james_oehring_mo")

        if broker == "anywho":
            from bs4 import BeautifulSoup

            scraper = AnyWhoFullProfileScraper(api_key="t")
            haystack = scraper._card_text(BeautifulSoup(html, "html.parser"), "Phone Numbers")
        else:
            haystack = html

        flattened = haystack.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
        for phone in profile.phoneNumbers:
            digits = "".join(c for c in phone["number"] if c.isdigit())
            assert digits in flattened, \
                f"{broker}: {phone['number']} does not occur in the page"

    @pytest.mark.parametrize("broker", ["fps", "npd", "anywho"])
    def test_no_asset_filenames_stored_as_emails(self, broker, fps, npd, anywho):
        profile = {"fps": fps, "npd": npd, "anywho": anywho}[broker]
        for email in profile.emailAddresses:
            assert not email.rsplit(".", 1)[-1] in (
                "png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js"
            ), f"{broker}: asset filename stored as email: {email}"

    @pytest.mark.parametrize("broker", ["fps", "npd", "anywho"])
    def test_no_headings_stored_as_people(self, broker, fps, npd, anywho):
        """FPS used to store 'Current & Past Contact Info' as an associate."""
        profile = {"fps": fps, "npd": npd, "anywho": anywho}[broker]
        people = list(getattr(profile, "relatives", []) or []) + \
                 list(getattr(profile, "familyMembers", []) or []) + \
                 list(getattr(profile, "associates", []) or [])
        for person in people:
            name = person["name"]
            assert "&" not in name and len(name.split()) <= 5, \
                f"{broker}: page furniture stored as a person: {name!r}"


class TestFps:
    def test_name_is_clean(self, fps):
        # Was "James Oehringin Cameron" -- h1 text concatenated without a break
        assert fps.fullName == "James Oehring"

    def test_age(self, fps):
        assert fps.age == 61

    def test_street_address(self, fps):
        assert fps.currentAddress["street"] == "413 Lovers Ln"
        assert_street_address(fps.currentAddress["formatted"], "fps profile")

    def test_geo_captured(self, fps):
        assert fps.currentAddress["latitude"].startswith("39.")

    def test_relatives_extracted(self, fps):
        # Previously empty, then silently capped at 10 despite 45 in the
        # page's JSON-LD -- MAX_RELATIVES raised so all of them come through.
        assert len(fps.relatives) == 45
        assert fps.relatives[0]["name"] == "Rickilinda R Oehring"

    def test_relative_demographics_matched_from_dom(self, fps):
        # Age/birth month live only in the DOM's Relatives section and were
        # previously dropped; matched to the JSON-LD name by (first, last)
        # since the DOM drops middle names/suffixes ("Robert Mctarsney" vs
        # "Robert J Mctarsney Jr").
        assert all("age" in r and "birthMonth" in r for r in fps.relatives)
        assert fps.relatives[0]["age"] == "65"
        assert fps.relatives[0]["birthMonth"] == "May 1961"

    def test_born_date(self, fps):
        # "Age 61, Born June 1965" -- the born half was ignored
        assert fps.bornDate == "June 1965"

    def test_only_real_phone(self, fps):
        assert [p["number"] for p in fps.phoneNumbers] == ["(816) 632-2218"]

    def test_phone_details(self, fps):
        # Type/carrier/first-reported sit right in the Phone Numbers section
        # next to the number this scraper already reads
        phone = fps.phoneNumbers[0]
        assert phone["type"] == "Landline"
        assert phone["carrier"]
        assert re.fullmatch(r'[A-Za-z]+ \d{4}', phone["firstReported"])

    def test_emails_are_personal(self, fps):
        assert "ja_studly@hotmail.com" in fps.emailAddresses
        assert not any("fastpeoplesearch" in e for e in fps.emailAddresses)

    def test_previous_addresses_from_html(self, fps):
        """
        FPS publishes only the current homeLocation in JSON-LD, so past
        addresses come from the rendered page -- and, as on the search page,
        the street lives in the anchor's title while the link text shows only
        city and state.
        """
        assert len(fps.previousAddresses) == 3
        formatted = [a["formatted"] for a in fps.previousAddresses]
        assert any("1225 Union AVE, Unit 502" in f for f in formatted)
        for address in fps.previousAddresses:
            assert_street_address(address["formatted"], "fps previous")
            assert re.fullmatch(r'\d{5}(-\d{4})?', address["postalCode"])

    def test_previous_addresses_have_county_and_recorded_date(self, fps):
        # Each address's own <dl> carries a county and "Recorded <date>" <dd>
        # right next to the link this scraper already reads
        for address in fps.previousAddresses:
            assert address["county"].endswith("County")
            assert re.fullmatch(r'[A-Za-z]+ \d{4}', address["recordedDate"])

    def test_current_address_not_repeated(self, fps):
        current = fps.currentAddress["street"].lower()
        assert current not in [
            (a.get("street") or "").lower() for a in fps.previousAddresses
        ]

    def test_property_details(self, fps):
        # Declared on Profile.properties but only beds/baths/sqft/built/value
        # were ever read; occupancy/ownership/land-use/class/lot-size live in
        # a separate #current_property_data box as clean <dt>/<dd> pairs
        details = fps.properties[0]
        assert details["occupancyType"] == "Owner Occupied"
        assert details["ownershipType"] == "Individual"
        assert details["landUse"] == "Single Family"
        assert details["propertyClass"] == "Residential"
        assert details["lotSqFt"] == 8712

    def test_no_aliases_when_page_has_none(self, fps):
        # James's fixture has no "Also Known As" section or JSON-LD
        # additionalName -- confirms this doesn't fabricate any
        assert fps.aliases == []

    def test_no_associates_when_page_has_none(self, fps):
        # James's fixture has no #associate-links section
        assert not any(r.get("source") == "associate" for r in fps.relatives)

    def test_employment(self, fps):
        assert fps.employment == [
            {"employer": "RINGLDR", "location": "Kansas City, MO", "title": "FOUNDER"}
        ]


class TestNpd:
    def test_identity(self, npd):
        assert npd.fullName == "James Oehring"
        assert npd.dateOfBirth == "1963"
        assert npd.age is not None

    def test_street_address(self, npd):
        # Was "Cameron, MO" -- city only
        assert npd.currentAddress["street"] == "413 Lovers Ln"

    def test_previous_addresses(self, npd):
        assert len(npd.previousAddresses) >= 1

    def test_phones(self, npd):
        assert {p["number"] for p in npd.phoneNumbers} == {
            "(816) 632-2218", "(816) 225-8592"
        }

    def test_phone_types(self, npd):
        # "(816) 632-2218 (Landline)" sits right next to the number this
        # scraper already reads; format_phones() used to hardcode "unknown"
        by_number = {p["number"]: p["type"] for p in npd.phoneNumbers}
        assert by_number["(816) 632-2218"] == "Landline"
        assert by_number["(816) 225-8592"] == "Mobile"

    def test_emails(self, npd):
        assert len(npd.emailAddresses) == 5
        assert "ja_studly@hotmail.com" in npd.emailAddresses

    def test_relatives(self, npd):
        assert [r["name"] for r in npd.relatives] == ["Rickilinda Oehring"]

    def test_previous_addresses_have_years_active(self, npd):
        # "Last reported in 2015" in #person-previous-address, matched to the
        # JSON-LD address by normalising away the comma-placement difference
        assert npd.previousAddresses, "fixture should have address history"
        for address in npd.previousAddresses:
            assert re.fullmatch(r'\d{4}', address["yearsActive"]), address


class TestAnyWho:
    def test_identity(self, anywho):
        # Was age 65; the header says 37 and the summary agrees
        assert anywho.fullName == "James A Oehring"
        assert anywho.age == 37

    def test_phones_with_carrier(self, anywho):
        by_number = {p["number"]: p for p in anywho.phoneNumbers}
        assert set(by_number) == {"(816) 225-8592", "(816) 632-2218"}
        assert by_number["(816) 225-8592"]["carrier"] == "AT&T"

    def test_carrier_has_no_ui_text(self, anywho):
        for phone in anywho.phoneNumbers:
            assert "More" not in phone["carrier"], phone

    def test_phone_location(self, anywho):
        # "816-225-8592Kansas City, MO•AT&T" -- the city/state half was
        # computed alongside carrier and discarded
        by_number = {p["number"]: p for p in anywho.phoneNumbers}
        assert by_number["(816) 225-8592"]["location"] == "Kansas City, MO"
        assert by_number["(816) 632-2218"]["location"] == "Cameron, MO"

    def test_emails_are_clean(self, anywho):
        # Flattening the card glued neighbouring words onto each address
        # ("jaoehring@gmail.com.show", "addressesjaoehring@gmail.comgmail")
        assert "jaoehring@gmail.com" in anywho.emailAddresses
        assert "james@ringldr.com" in anywho.emailAddresses
        for email in anywho.emailAddresses:
            assert not email.endswith(".show")
            assert email.count("@") == 1

    def test_current_address_from_header(self, anywho):
        """
        The header block labels the current address explicitly. Reading it from
        the Address History card instead gave the wrong one, because that
        card's DOM order does not track recency.
        """
        assert anywho.currentAddress["street"] == "1225 Union Ave, Apt 502"
        assert anywho.currentAddress["city"] == "Kansas City"
        # The header is the only place the postal code appears
        assert anywho.currentAddress["postalCode"] == "64101"

    def test_current_address_agrees_with_summary(self, anywho):
        from anywho_html_scraper import AnyWhoHtmlScraper

        summary = AnyWhoHtmlScraper(api_key="t")._extract_summary_from_html(
            (FIXTURES / "anywho" / "james_oehring_mo.html").read_text()
        )[0]
        assert summary.address.startswith("1225 Union Ave")
        assert anywho.currentAddress["formatted"].startswith("1225 Union Ave")

    def test_address_history_is_complete(self, anywho):
        """
        The card heading states the count -- "Address History (11)". Extracting
        fewer means rows are being dropped: requiring the locality child to
        match exactly kept only the rows without a residency date range, 3 of
        11, and nothing failed.
        """
        html = load("anywho", "james_oehring_mo")
        claimed = int(re.search(r'Address History \((\d+)\)', html).group(1))
        # currentAddress is lifted out of the history, so one fewer remains
        assert len(anywho.previousAddresses) == claimed - 1, (
            f"card claims {claimed} addresses, extracted "
            f"{len(anywho.previousAddresses)} + 1 current"
        )

    def test_address_history(self, anywho):
        assert len(anywho.previousAddresses) >= 3
        for address in anywho.previousAddresses:
            # The unit used to run into the city: "Apt 502Kansas, City"
            assert not address["city"].startswith("City")
            assert_street_address(address["formatted"], "anywho profile")

    def test_residency_years_captured(self, anywho):
        dated = [a for a in anywho.previousAddresses if a.get("years")]
        assert dated, "no residency date ranges captured"
        for address in dated:
            assert re.fullmatch(r'\d{4}-\d{4}', address["years"]), address

    def test_current_address_not_repeated_in_history(self, anywho):
        formatted = anywho.currentAddress.get("formatted")
        assert formatted not in [a["formatted"] for a in anywho.previousAddresses]

    def test_property_type_captured(self, anywho):
        # "James lived here in this Single Family Residential from 2005 to
        # 2025" -- a sibling of the street/city-state children this scraper
        # already reads, previously ignored
        typed = [a for a in anywho.previousAddresses if a.get("propertyType")]
        assert typed, "no property types captured"
        for address in typed:
            assert "lived here" not in address["propertyType"]
            assert not re.search(r'\bfrom\s+\d{4}\s+to\s+\d{4}$', address["propertyType"])

    def test_family_members(self, anywho):
        assert [f["name"] for f in anywho.familyMembers] == ["Rickilinda Oehring"]

    def test_family_member_demographics(self, anywho):
        # "Female•65" sits right below the name heading this scraper already
        # reads -- gender/age of the relative, not of the profile subject
        assert anywho.familyMembers[0]["gender"] == "Female"
        assert anywho.familyMembers[0]["age"] == 65

    def test_aliases(self, anywho):
        # "Aka: James Allen Oehring Jr." -- no Profile.aliases field existed
        assert anywho.aliases == ["James Allen Oehring Jr."]

    def test_legal_records(self, anywho):
        # #court-records ("Legal Records (4)") -- entirely unextracted before
        assert anywho.legalRecords["nationwideCount"] == 4
        assert anywho.legalRecords["countyRecords"] == {
            "location": "Dekalb, Missouri", "count": 2,
        }


class TestSecondFixtures:
    """Guard against overfitting to the oehring page."""

    def test_fps_clark(self):
        profile = FPSFullProfileScraper(api_key="t")._parse_profile_html(
            load("fps", "lucas_clark_mo"), "pid"
        )
        assert profile.fullName == "Lucas Clark"
        assert profile.currentAddress["street"]
        for phone in profile.phoneNumbers:
            assert FULL_PHONE.match(phone["number"])
        # A longer history than oehring's, so this guards the parser against
        # being tuned to a single page
        assert len(profile.previousAddresses) > 5
        for address in profile.previousAddresses:
            assert_street_address(address["formatted"], "fps clark previous")
        assert all(p.get("type") and p.get("carrier") for p in profile.phoneNumbers)
        assert all("age" in r for r in profile.relatives)
        assert profile.bornDate == "December 1991"
        # Fields only this fixture's property box has, unlike oehring's
        details = profile.properties[0]
        assert details["subdivision"] == "Rockhill Manor"
        assert details["estimatedEquity"] == 39813
        assert details["lastSaleAmount"] == 451535
        assert details["lastSaleDate"] == "2023-04-19"
        # Fields only this fixture's #aka-links/#associate-links/employment/
        # education sections have, unlike oehring's
        assert set(profile.aliases) == {"Lucas C Ward", "Clark Lucas"}
        associates = [r for r in profile.relatives if r.get("source") == "associate"]
        assert len(associates) == 31
        assert all("age" in a for a in associates)
        assert profile.employment[0]["employer"] == "EHAWK, INC."
        assert len(profile.jobHistory) == 9
        assert all(j.get("title") for j in profile.jobHistory)
        assert profile.education[0]["school"] == "NORTHWEST MISSOURI STATE UNIVERSITY"

    def test_anywho_rodgers(self):
        profile = AnyWhoFullProfileScraper(api_key="t")._parse_profile_html(
            load("anywho", "chris_rodgers_ks"), "pid"
        )
        assert profile.fullName == "Chris M Rodgers"
        assert profile.age == 47
        assert profile.emailAddresses
        for email in profile.emailAddresses:
            assert email.count("@") == 1
        assert all(p.get("location") for p in profile.phoneNumbers)
        assert any(a.get("propertyType") for a in profile.previousAddresses)
        # "Aka: Christopher Michael Rodgers, Kathy H Rodgers or Casey Rodgers"
        # -- a natural-language list mixing ", " and " or " separators
        assert profile.aliases == [
            "Christopher Michael Rodgers", "Kathy H Rodgers", "Casey Rodgers",
        ]
        assert all("gender" in f and "age" in f for f in profile.familyMembers)
        # No county-level breakdown on this fixture, nationwide count only
        assert "countyRecords" not in profile.legalRecords
        assert profile.legalRecords["nationwideCount"] == 34
