#!/usr/bin/env python3
"""
FPS Full Profile Scraper (Cost-Efficient Version)

Uses context.dev HTML method to fetch and parse full profile pages.
Extracts: phones, emails, relatives, associates, properties, addresses.

Cost: ~0.001 per request (10x cheaper than Extract API)
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from bs4 import BeautifulSoup
from context.dev import ContextDev

from targets.fps.models import Profile
from jsonld_profile import (
    extract_person,
    format_phone,
    format_phones,
    related_names,
    split_home_locations,
)

logger = logging.getLogger(__name__)


class FPSFullProfileScraper:
    """Scrapes full profiles from FastPeopleSearch using context.dev HTML method"""

    # Was 10 -- silently dropped 36-39 of 46-49 relatives on real profiles
    # (James/Lucas fixtures). Raised with headroom above observed maxima.
    MAX_RELATIVES = 60
    MAX_EMAILS = 10

    # The site's own addresses, plus anything that signals a non-personal mailbox
    EXCLUDED_EMAIL_FRAGMENTS = (
        'fastpeoplesearch.com', 'support@', 'noreply@', 'no-reply@',
        'admin@', 'info@', 'notifications@', 'example.com', 'sentry.io',
    )

    # Sprite filenames such as "linkedin@2x.a7ffbfd3.png" match an email regex
    ASSET_EXTENSIONS = ('png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'css', 'js')

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with context.dev client"""
        self.client = ContextDev(api_key=api_key)

    def scrape_profile(self, profile_url: str, profile_id: str = "") -> Optional[Profile]:
        """
        Scrape a full profile page.

        Args:
            profile_url: Direct link to person's profile (e.g., /james-oehring_id_G369...)
            profile_id: Optional profile ID for tracking

        Returns:
            Profile object with enriched data, or None if failed
        """
        if not profile_url:
            return None

        # Ensure URL is absolute
        if not profile_url.startswith("http"):
            profile_url = f"https://www.fastpeoplesearch.com{profile_url}"

        logger.info(f"Scraping FPS profile: {profile_url}")

        try:
            # Fetch profile page using context.dev HTML method
            html_result = self.client.web.web_scrape_html(url=profile_url)

            if not html_result or not html_result.html:
                logger.warning(f"No HTML returned for {profile_url}")
                return None

            # Parse profile
            profile = self._parse_profile_html(html_result.html, profile_id or profile_url)
            return profile

        except Exception as e:
            logger.error(f"Error scraping FPS profile {profile_url}: {e}", exc_info=True)
            return None

    def _parse_profile_html(self, html: str, profile_id: str) -> Optional[Profile]:
        """
        Parse a full profile page.

        Reads the schema.org Person block rather than regexing the page. The
        previous implementation matched phone patterns against raw HTML, which
        also matched the digits inside the profile URL id -- turning
        /james-oehring_id_G3697305023830937972 into "(369) 730-5023".
        """
        try:
            person = extract_person(html)
            if not person:
                logger.warning("No JSON-LD Person block on FPS profile page")
                return None

            soup = BeautifulSoup(html, "html.parser")
            profile = Profile(profileId=profile_id)

            profile.fullName = (person.get("name") or "").strip()
            if not profile.fullName:
                given = (person.get("givenName") or "").strip()
                family = (person.get("familyName") or "").strip()
                profile.fullName = " ".join(p for p in (given, family) if p)

            profile.age = self._extract_age(soup)
            profile.bornDate = self._extract_born_date(soup)
            profile.phoneNumbers = format_phones(person.get("telephone"))
            self._apply_phone_details(profile.phoneNumbers, soup)
            profile.relatives = related_names(person.get("relatedTo"), limit=self.MAX_RELATIVES)
            self._apply_relative_details(profile.relatives, soup)
            profile.currentAddress, profile.previousAddresses = split_home_locations(
                person.get("homeLocation")
            )
            # FPS publishes only the current homeLocation in JSON-LD; the past
            # addresses live in the rendered page.
            profile.previousAddresses.extend(
                self._extract_previous_addresses(soup, profile.currentAddress)
            )
            profile.emailAddresses = self._extract_emails(html)

            property_details = self._extract_current_address_property(soup)
            if property_details:
                profile.properties = [property_details]

            logger.debug(
                f"Parsed FPS profile: {profile.fullName}, "
                f"{len(profile.emailAddresses)} emails, "
                f"{len(profile.phoneNumbers)} phones, "
                f"{len(profile.relatives)} relatives"
            )

            return profile if profile.fullName else None

        except Exception as e:
            logger.error(f"Error parsing FPS profile HTML: {e}", exc_info=True)
            return None

    # Link titles read "Search people who live at 1225 Union AVE, Unit 502,
    # Kansas City MO 64101" -- wording varies ("living at", "at the address"),
    # so the address is taken as everything after the last " at ".
    ADDRESS_TITLE = re.compile(r'\bat (?:the address )?(.+)$', re.IGNORECASE)
    ADDRESS_PARTS = re.compile(
        r"^(.*),\s*([A-Za-z .'\-]+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$"
    )

    @classmethod
    def _address_key(cls, address: Dict[str, str]) -> str:
        """Identity of an address, ignoring case and punctuation."""
        street = (address.get("street") or "").lower().replace(".", "")
        return re.sub(r'\s+', ' ', street).strip()

    # "Jackson County" / "Recorded July 2020" -- the two <dd>s sitting next to
    # each address link, previously ignored in favour of the link alone.
    RECORDED = re.compile(r'Recorded\s+(.+)', re.IGNORECASE)

    @classmethod
    def _extract_previous_addresses(cls, soup, current: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Past addresses from the "Previous Addresses" section.

        The visible link text is only the city and state; the full street
        address is in the anchor's title attribute, same as on the search page.
        Each address's <dl> also carries a county and a "Recorded <date>" <dd>,
        sitting right next to the link.
        """
        section = soup.select_one('#previous-addresses')
        if not section:
            return []

        current_key = cls._address_key(current)
        addresses: List[Dict[str, str]] = []
        seen = {current_key} if current_key else set()

        for dl in section.select('dl'):
            link = dl.find('a', href=re.compile(r'/address/'))
            if not link:
                continue
            title = (link.get('title') or '').strip()
            match = cls.ADDRESS_TITLE.search(title)
            if not match:
                continue

            formatted = re.sub(r'\s+', ' ', match.group(1)).strip()
            parts = cls.ADDRESS_PARTS.match(formatted)
            if parts:
                street, city, state, postal = parts.groups()
                address = {
                    "street": street.strip(),
                    "city": city.strip(),
                    "state": state,
                    "postalCode": postal,
                    "formatted": formatted,
                }
            else:
                address = {"formatted": formatted}

            key = cls._address_key(address) or formatted.lower()
            if key in seen:
                continue
            seen.add(key)

            for dd in dl.select('dd'):
                text = dd.get_text(strip=True)
                recorded = cls.RECORDED.match(text)
                if recorded:
                    address["recordedDate"] = recorded.group(1).strip()
                elif text.lower().endswith('county'):
                    address["county"] = text

            addresses.append(address)

        return addresses

    @staticmethod
    def _extract_age(soup) -> Optional[int]:
        """
        Read the age from the profile header.

        Scoped to the header because "Age NN" appears repeatedly further down
        the page for relatives and neighbours.
        """
        header = soup.select_one("#details-summary, .details-summary, h1")
        region = header.parent if header and header.parent else soup
        match = re.search(r"Age\s+(\d{1,3})", region.get_text(" ", strip=True))
        if match:
            age = int(match.group(1))
            return age if 0 < age < 150 else None
        return None

    @staticmethod
    def _extract_born_date(soup) -> str:
        """
        Birth month/year from the profile header, e.g. "Age 61, Born June
        1965" -- sitting right next to the age this scraper already reads,
        previously discarded.
        """
        header = soup.select_one("#details-summary, .details-summary, h1")
        region = header.parent if header and header.parent else soup
        match = re.search(r"Born\s+([A-Za-z]+\s+\d{4})", region.get_text(" ", strip=True))
        return match.group(1) if match else ""

    @staticmethod
    def _name_key(name: str) -> tuple:
        """
        (first, last) name key, ignoring middle names and suffixes, so a
        JSON-LD name ("Robert J Mctarsney Jr") matches its DOM counterpart
        ("Robert Mctarsney").
        """
        suffixes = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}
        tokens = [t.strip('.') for t in name.split() if t.strip('.')]
        while tokens and tokens[-1].lower() in suffixes:
            tokens.pop()
        if not tokens:
            return ("", "")
        return (tokens[0].lower(), tokens[-1].lower())

    @classmethod
    def _apply_phone_details(cls, phones: List[Dict[str, str]], soup) -> None:
        """
        Fill in type/carrier/firstReported from the "Phone Numbers" section,
        matched to the JSON-LD-derived numbers already in `phones`. JSON-LD
        only has the bare digits (format_phones hardcodes "type": "unknown"),
        but the rendered page carries real structured detail per number.
        """
        section = soup.select_one('#phone_number_section')
        if not section:
            return

        details: Dict[str, Dict[str, str]] = {}
        for dl in section.select('dl'):
            link = dl.find('a')
            if not link:
                continue
            number = format_phone(link.get_text(strip=True))
            if not number:
                continue
            entry: Dict[str, str] = {}
            for dd in dl.select('dd'):
                text = dd.get_text(" ", strip=True)
                if text.lower().startswith('first reported'):
                    span = dd.select_one('span')
                    entry['firstReported'] = (
                        span.get_text(strip=True) if span
                        else text[len('first reported'):].strip()
                    )
                elif 'type' not in entry:
                    entry['type'] = text
                elif 'carrier' not in entry:
                    entry['carrier'] = text
            if entry:
                details[number] = entry

        for phone in phones:
            extra = details.get(phone.get('number', ''))
            if extra:
                phone.update(extra)

    @classmethod
    def _apply_relative_details(cls, relatives: List[Dict[str, str]], soup) -> None:
        """
        Fill in age/birth month from the "Relatives" section, matched to the
        JSON-LD-derived names already in `relatives` by (first, last) name --
        JSON-LD carries full middle names/suffixes the DOM doesn't.
        """
        section = soup.select_one('#relative-links')
        if not section:
            return

        details: Dict[tuple, Dict[str, str]] = {}
        for dl in section.select('dl'):
            link = dl.select_one('dt a')
            dd = dl.select_one('dd')
            if not link or not dd:
                continue
            key = cls._name_key(link.get_text(strip=True))
            if key == ("", "") or key in details:
                continue
            match = re.match(
                r'Age\s+(\d{1,3})\s*\(([A-Za-z]+\s+\d{4})\)', dd.get_text(strip=True)
            )
            if match:
                details[key] = {"age": match.group(1), "birthMonth": match.group(2)}

        for relative in relatives:
            extra = details.get(cls._name_key(relative.get('name', '')))
            if extra:
                relative.update(extra)

    # Labels in the #current_property_data <dl> pairs not already covered by
    # the free-text regexes below (beds/baths/sqft/built/value/county). Value
    # keys ending in these three get their currency/commas stripped to ints;
    # the rest are kept as plain text.
    PROPERTY_LABEL_MAP = {
        "Estimated Equity": "estimatedEquity",
        "Last Sale Amount": "lastSaleAmount",
        "Last Sale Date": "lastSaleDate",
        "Occupancy Type": "occupancyType",
        "Ownership Type": "ownershipType",
        "Land Use": "landUse",
        "Property Class": "propertyClass",
        "Subdivision": "subdivision",
        "Lot SqFt.": "lotSqFt",
    }
    PROPERTY_NUMERIC_FIELDS = {"estimatedEquity", "lastSaleAmount", "lotSqFt"}

    def _extract_current_address_property(self, soup) -> Dict[str, Any]:
        """
        Residence detail for the current address -- beds, baths, square
        footage, year built, estimated value, county, and how long they've
        lived there. FPS is the only one of the four brokers that publishes
        this; declared in the Profile dataclass but never actually extracted
        until now.

        Example markup under #current_address_section:
            <h2>Current Address <span>(Since October 2005)</span></h2>
            ...413 Lovers Ln, Cameron MO 64429... Dekalb County
            3 Beds | 1 Bath | 960 SqFt. | Built in 1981
            <dl><dt>Estimated Value</dt><dd>$189,000</dd></dl>
        """
        section = soup.select_one("#current_address_section")
        if not section:
            return {}

        result: Dict[str, Any] = {}

        since_span = section.select_one("h2 span")
        if since_span:
            match = re.search(r"Since\s+(.+)", since_span.get_text(strip=True), re.IGNORECASE)
            if match:
                result["residedSince"] = match.group(1).strip(") ")

        # All the residence-detail fields are scattered across a few text
        # nodes rather than tagged individually, so pull the whole section's
        # text and pick each figure out with its own pattern.
        text = section.get_text(" ", strip=True)

        beds = re.search(r"(\d+(?:\.\d+)?)\s*Beds?\b", text, re.IGNORECASE)
        baths = re.search(r"(\d+(?:\.\d+)?)\s*Baths?\b", text, re.IGNORECASE)
        sqft = re.search(r"([\d,]+)\s*SqFt", text, re.IGNORECASE)
        built = re.search(r"Built in (\d{4})", text, re.IGNORECASE)
        value = re.search(r"Estimated Value\s*\$?([\d,]+)", text, re.IGNORECASE)
        county = re.search(r"([A-Za-z]+ County)", text)

        if beds:
            result["beds"] = beds.group(1)
        if baths:
            result["baths"] = baths.group(1)
        if sqft:
            result["squareFeet"] = int(sqft.group(1).replace(",", ""))
        if built:
            result["yearBuilt"] = int(built.group(1))
        if value:
            result["estimatedValue"] = int(value.group(1).replace(",", ""))
        if county:
            result["county"] = county.group(1).strip()

        # The rest (equity, last sale, occupancy/ownership/land-use/class,
        # subdivision, lot size) live in a separate #current_property_data
        # box as clean <dt>/<dd> pairs rather than free text -- declared in
        # the Profile dataclass's properties field but never read until now.
        property_data = soup.select_one("#current_property_data")
        if property_data:
            for dl in property_data.select("dl"):
                dt = dl.select_one("dt")
                dd = dl.select_one("dd")
                if not dt or not dd:
                    continue
                key = self.PROPERTY_LABEL_MAP.get(dt.get_text(strip=True))
                if not key or key in result:
                    continue
                value = dd.get_text(strip=True)
                if key in self.PROPERTY_NUMERIC_FIELDS:
                    digits = re.sub(r"[^\d]", "", value)
                    if digits:
                        result[key] = int(digits)
                elif value:
                    result[key] = value

        return result

    def _extract_emails(self, html: str) -> List[str]:
        """
        Collect personal email addresses from the page.

        FPS does not publish emails in JSON-LD, so this reads the rendered page
        and drops the site's own addresses and any asset filename that happens
        to contain an @ (sprite images like "linkedin@2x.a7ffbfd3.png" parse as
        valid addresses otherwise).
        """
        found = re.findall(r"[a-zA-Z0-9._%%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html)

        emails: List[str] = []
        for email in found:
            email = email.lower()
            if any(bad in email for bad in self.EXCLUDED_EMAIL_FRAGMENTS):
                continue
            if email.rsplit(".", 1)[-1] in self.ASSET_EXTENSIONS:
                continue
            if email not in emails:
                emails.append(email)
        return emails[: self.MAX_EMAILS]
