#!/usr/bin/env python3
"""
AnyWho Full Profile Scraper

Uses context.dev HTML method to fetch and parse full profile pages.
Extracts: phones, emails, relatives, properties, addresses.
"""

import logging
import re
from typing import Dict, Any, Optional, List

from bs4 import BeautifulSoup
from context.dev import ContextDev

from targets.anywho.models import Profile
from anywho_html_scraper import AnyWhoHtmlScraper

logger = logging.getLogger(__name__)


class AnyWhoFullProfileScraper:
    """Scrapes full profiles from AnyWho using context.dev HTML method"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with context.dev client"""
        self.client = ContextDev(api_key=api_key)

    def scrape_profile(self, profile_url: str, profile_id: str = "") -> Optional[Profile]:
        """
        Scrape a full profile page.

        Args:
            profile_url: Direct link to person's profile
            profile_id: Optional profile ID for tracking

        Returns:
            Profile object with enriched data, or None if failed
        """
        if not profile_url:
            return None

        # Ensure URL is absolute
        if not profile_url.startswith("http"):
            profile_url = f"https://www.anywho.com{profile_url}"

        logger.info(f"Scraping AnyWho profile: {profile_url}")

        try:
            # Fetch profile page
            html_result = self.client.web.web_scrape_html(url=profile_url)

            if not html_result or not html_result.html:
                logger.warning(f"No HTML returned for {profile_url}")
                return None

            # Parse profile
            profile = self._parse_profile_html(html_result.html, profile_id or profile_url)
            return profile

        except Exception as e:
            logger.error(f"Error scraping AnyWho profile {profile_url}: {e}", exc_info=True)
            return None

    # Profile sections are cards keyed by their heading text
    CARD_CLASS = re.compile(r'bg-white')

    # The profile page blurs values exactly like the search page, so reuse the
    # summary scraper's reconstruction rather than reimplementing it. Bound as a
    # class attribute so the helper's internal recursion resolves on instances
    # of this class too; SKIP_TAGS comes along because the helper reads it.
    SKIP_TAGS = AnyWhoHtmlScraper.SKIP_TAGS
    _reconstruct_with_data_content = AnyWhoHtmlScraper._reconstruct_with_data_content

    MAX_VALUES = 12

    EXCLUDED_EMAIL_FRAGMENTS = (
        'anywho.com', 'support@', 'noreply@', 'no-reply@', 'admin@',
        'info@', 'example.com', 'sentry.io', 'notifications@',
    )
    ASSET_EXTENSIONS = ('png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'css', 'js')

    def _parse_profile_html(self, html: str, profile_id: str) -> Optional[Profile]:
        """
        Parse an AnyWho profile page.

        AnyWho publishes no schema.org Person block, so this reads the rendered
        cards -- via the same data-content reconstruction the summary scraper
        uses, since the profile page blurs values the same way (50 blurred
        spans on a typical page).

        The previous implementation regexed the whole page and stored sprite
        filenames ("linkedin@2x.a7ffbfd3.png") as email addresses and a form
        placeholder ("(626) 555-5555") as a phone number.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            profile = Profile(profileId=profile_id)

            # Header carries both name and age: "James A Oehring , 37"
            h1 = soup.find("h1")
            if h1:
                header = self._clean(self._reconstruct(h1))
                match = re.match(r'^(.*?)\s*,\s*(\d{1,3})\s*$', header)
                if match:
                    profile.fullName = match.group(1).strip()
                    age = int(match.group(2))
                    profile.age = age if 0 < age < 150 else None
                else:
                    profile.fullName = header

            profile.phoneNumbers = self._extract_phones(soup)
            profile.emailAddresses = self._extract_emails(soup)
            # The header block labels the current address explicitly; the
            # Address History card below it is an unordered history whose DOM
            # order does not track recency.
            profile.currentAddress = self._extract_current_address(soup)
            # Compared on street/city/state, not the formatted string: the
            # header carries a postal code the history rows do not, so the same
            # address renders differently in each place.
            current_key = self._address_key(profile.currentAddress)
            profile.previousAddresses = [
                address for address in self._extract_addresses(soup)
                if self._address_key(address) != current_key
            ]
            profile.familyMembers = self._extract_relatives(soup)

            logger.debug(
                f"Parsed AnyWho profile: {profile.fullName}, "
                f"{len(profile.emailAddresses)} emails, "
                f"{len(profile.phoneNumbers)} phones, "
                f"{len(profile.familyMembers)} family"
            )

            return profile if profile.fullName else None

        except Exception as e:
            logger.error(f"Error parsing AnyWho profile HTML: {e}", exc_info=True)
            return None

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r'\s+', ' ', text or "").strip()

    def _reconstruct(self, element) -> str:
        """Reuse the summary scraper's blurred-value reconstruction."""
        return self._reconstruct_with_data_content(element)

    @staticmethod
    def _address_key(address: Dict[str, str]) -> str:
        """Identity of an address, ignoring formatting and postal code."""
        return "|".join(
            (address.get(part) or "").lower().replace(".", "").strip()
            for part in ("street", "city", "state")
        )

    # Header rows read "CURRENT ADDRESS:1225 Union Ave, Apt 502, Kansas City, MO, 64101"
    HEADER_ADDRESS = re.compile(
        r"^(.*?),\s*([A-Za-z .'\-]+),\s*([A-Z]{2})(?:,\s*(\d{5}(?:-\d{4})?))?$"
    )

    def _header_value(self, soup, label: str) -> str:
        """
        Value of a labelled row in the profile header block.

        The header is the only place AnyWho states which address is current,
        and it is the only place the postal code appears.
        """
        pattern = re.compile(rf'^\s*{re.escape(label)}\s*:?\s*$', re.IGNORECASE)
        for node in soup.find_all(string=pattern):
            row = node.parent.parent if node.parent else None
            if not row:
                continue
            text = self._clean(self._reconstruct(row))
            match = re.match(rf'^{re.escape(label)}\s*:?\s*(.+)$', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_current_address(self, soup) -> Dict[str, str]:
        """Parse the header's CURRENT ADDRESS row."""
        value = self._header_value(soup, "Current Address")
        if not value:
            return {}

        # Trailing bullet separates it from any "+ N" more indicator
        value = value.split('•')[0].strip()

        match = self.HEADER_ADDRESS.match(value)
        if not match:
            return {"formatted": value}

        street, city, state, postal = match.groups()
        address = {
            "street": self._clean(street),
            "city": self._clean(city),
            "state": state,
            "formatted": self._clean(value),
        }
        if postal:
            address["postalCode"] = postal
        return address

    def _card(self, soup, label: str):
        """The section card whose heading contains label."""
        for heading in soup.find_all(['h2', 'h3']):
            if label.lower() in heading.get_text().lower():
                card = heading.find_parent('div', class_=self.CARD_CLASS)
                if card:
                    return card
        return None

    def _card_text(self, soup, label: str) -> str:
        """Reconstructed text of the section card whose heading contains label."""
        card = self._card(soup, label)
        return self._clean(self._reconstruct(card)) if card else ""

    def _extract_phones(self, soup) -> List[Dict[str, str]]:
        """
        Phones live in the "Phone Numbers" card as 816-225-8592, each followed
        by its city and carrier: "816-225-8592Kansas City, MO-AT&T".
        Scoped to that card so form placeholders elsewhere cannot match.
        """
        text = self._card_text(soup, "Phone Numbers")
        if not text:
            return []

        phones: List[Dict[str, str]] = []
        seen = set()
        matches = list(re.finditer(r'(\d{3})-(\d{3})-(\d{4})', text))
        for i, match in enumerate(matches):
            number = f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
            if number in seen:
                continue
            seen.add(number)

            # Text between this number and the next describes it
            tail = text[match.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
            carrier = ""
            parts = [p.strip() for p in tail.split('•') if p.strip()]
            if len(parts) > 1:
                carrier = self.UI_TAIL.split(parts[1])[0].strip()[:60]

            phones.append({"number": number, "type": "unknown", "carrier": carrier})

        return phones[: self.MAX_VALUES]

    EMAIL = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

    # "Kansas City, MO"
    CITY_STATE = re.compile(r"([A-Za-z .'\-]+),\s*([A-Z]{2})")

    # Cards end with call-to-action text that runs straight into the last value
    UI_TAIL = re.compile(r'(?:View|Show|Unlock|See)\s*[-+]?\d*\s*(?:More|Less)?', re.IGNORECASE)

    # "1225 Union Ave, Apt 502Kansas City, MO" -- street, city, state.
    # The street is anchored on its type token, otherwise the city name runs
    # into the suffix and "413 Lovers Ln" + "Cameron" splits as
    # "413 Lovers" + "LnCameron".
    STREET_TYPES = (
        r'St|Ave|Rd|Dr|Ln|Ter|Ct|Blvd|Way|Pl|Cir|Pkwy|Trl|Hwy|Sq|Aly|Loop|Run|Xing|Pt'
    )
    ADDRESS = re.compile(
        r'(\d+\s+[A-Za-z0-9.\'\- ]*?\b(?:' + STREET_TYPES + r')\b\.?'
        r'(?:\s*,?\s*(?:Apt|Ste|Unit|#)\s*[A-Za-z0-9\-]+)?)'
        r'\s*,?\s*([A-Z][A-Za-z .\'\-]+?),\s*([A-Z]{2})'
    )

    def _extract_emails(self, soup) -> List[str]:
        """
        Emails from the "Email Contacts" card.

        Matched against whole elements rather than the card's flattened text:
        the card renders each address next to its provider and profile count
        with no separating whitespace ("jaoehring@gmail.comgmail-0 Profiles"),
        so a regex over the flattened string bleeds the neighbouring words into
        the address.
        """
        card = self._card(soup, "Email Contacts")
        if not card:
            return []

        emails: List[str] = []
        for element in card.find_all(['div', 'span', 'li', 'a', 'p']):
            value = self._clean(self._reconstruct(element)).lower()
            if not self.EMAIL.fullmatch(value):
                continue
            if any(bad in value for bad in self.EXCLUDED_EMAIL_FRAGMENTS):
                continue
            if value.rsplit('.', 1)[-1] in self.ASSET_EXTENSIONS:
                continue
            if value not in emails:
                emails.append(value)
        return emails[: self.MAX_VALUES]

    def _extract_addresses(self, soup) -> List[Dict[str, str]]:
        """
        Addresses from the "Address History" card, most recent first.

        Matched per element for the same reason as emails: flattened, an entry
        reads "1225 Union Ave, Apt 502Kansas City, MO-2020-2020", and the
        trailing year of one entry runs into the house number of the next
        ("2020380 W 22nd St").
        """
        card = self._card(soup, "Address History")
        if not card:
            return []

        addresses: List[Dict[str, str]] = []
        seen = set()
        for element in card.find_all(['div', 'li']):
            # Each row keeps street and "City, ST" in separate child elements.
            # Read them individually: flattened, the unit runs into the city
            # ("Apt 502Kansas City, MO") with no boundary to split on.
            children = [
                self._clean(self._reconstruct(child))
                for child in element.children
                if getattr(child, 'name', None)
            ]
            children = [c for c in children if c]
            if len(children) < 2 or not children[0][:1].isdigit():
                continue

            # The locality child also carries the residency date range when the
            # record has one ("Cameron, MO•2005-2025"); everything from the
            # bullet on is dropped. Requiring a full match here silently kept
            # only the rows that happen to lack dates -- 3 of 11.
            locality = self.CITY_STATE.fullmatch(children[1].split('•')[0].strip())
            if not locality:
                continue

            street = children[0]
            city = self._clean(locality.group(1))
            state = locality.group(2)
            years = re.search(r'(\d{4})\s*-\s*(\d{4})', children[1])
            formatted = f"{street}, {city}, {state}"
            if formatted in seen:
                continue
            seen.add(formatted)
            address = {
                "street": street, "city": city, "state": state, "formatted": formatted,
            }
            if years:
                # Residency range, e.g. 2005-2025 -- useful for recency ranking
                address["years"] = f"{years.group(1)}-{years.group(2)}"
            addresses.append(address)
        return addresses[: self.MAX_VALUES]

    def _extract_relatives(self, soup) -> List[Dict[str, Any]]:
        """
        Family members appear as "Relative data result: <Name>" headings,
        optionally followed by "Female-65".
        """
        relatives: List[Dict[str, Any]] = []
        seen = set()
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            text = self._clean(self._reconstruct(heading))
            match = re.match(r'Relative data result:\s*(.+)$', text, re.IGNORECASE)
            if not match:
                continue
            name = match.group(1).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            relatives.append({"name": name})
        return relatives[: self.MAX_VALUES]
