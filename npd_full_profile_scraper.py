#!/usr/bin/env python3
"""
NPD (National Public Data) Full Profile Scraper

Uses context.dev HTML method to fetch and parse full profile pages.
Extracts: phones, emails, relatives, associates, properties, addresses.
"""

import logging
import re
from typing import Dict, Any, Optional, List

from bs4 import BeautifulSoup
from context.dev import ContextDev

from targets.npd.models import Profile
from jsonld_profile import (
    age_from_birth_date,
    extract_person,
    format_phone,
    format_phones,
    related_names,
    split_home_locations,
)

logger = logging.getLogger(__name__)


class NPDFullProfileScraper:
    """Scrapes full profiles from National Public Data using context.dev HTML method"""

    # MAX_RELATIVES uses the same shared related_names() helper as FPS, which
    # was confirmed dropping 36-39 of 46-49 relatives there -- raised here too
    # for the same reason, even though this profile's own relatives happened
    # to stay under the old cap.
    MAX_RELATIVES = 60
    MAX_EMAILS = 10
    # Was 10 -- silently dropped 26 of 36 associates on a real profile
    # (James Oehring fixture). Raised with headroom above observed maxima.
    MAX_ASSOCIATES = 50

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
            profile_url = f"https://www.nationalpublicdata.com{profile_url}"

        logger.info(f"Scraping NPD profile: {profile_url}")

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
            logger.error(f"Error scraping NPD profile {profile_url}: {e}", exc_info=True)
            return None

    def _parse_profile_html(self, html: str, profile_id: str) -> Optional[Profile]:
        """
        Parse a full profile page from its schema.org Person block.

        NPD publishes everything -- phones, emails, addresses, relatives -- in
        JSON-LD; the rendered card shows only name, age and city/state. The
        previous implementation regexed the page and produced numbers like
        (611) 503-8382 that appear nowhere as phone numbers.
        """
        try:
            person = extract_person(html)
            if not person:
                logger.warning("No JSON-LD Person block on NPD profile page")
                return None

            soup = BeautifulSoup(html, "html.parser")
            profile = Profile(profileId=profile_id)
            profile.fullName = (person.get("name") or "").strip()

            birth = person.get("birthDate")
            if birth:
                profile.dateOfBirth = str(birth)
                profile.age = age_from_birth_date(birth)

            profile.phoneNumbers = format_phones(person.get("telephone"))
            self._apply_phone_types(profile.phoneNumbers, soup)
            profile.relatives = related_names(person.get("relatedTo"), limit=self.MAX_RELATIVES)
            profile.currentAddress, profile.previousAddresses = split_home_locations(
                # NPD capitalises the key, unlike schema.org's homeLocation
                person.get("HomeLocation") or person.get("homeLocation")
            )
            self._apply_address_years(profile.previousAddresses, soup)

            emails = person.get("email") or []
            if isinstance(emails, str):
                emails = [emails]
            profile.emailAddresses = [e.strip() for e in emails if e and e.strip()][: self.MAX_EMAILS]

            # Associated people aren't in JSON-LD -- only the rendered
            # "Associated" section has them, unlike everything else on this
            # page. Declared in the Profile dataclass but never actually
            # extracted until now.
            profile.associates = self._extract_associates(soup)

            logger.debug(
                f"Parsed NPD profile: {profile.fullName}, "
                f"{len(profile.emailAddresses)} emails, "
                f"{len(profile.phoneNumbers)} phones, "
                f"{len(profile.relatives)} relatives, "
                f"{len(profile.associates)} associates"
            )

            return profile if profile.fullName else None

        except Exception as e:
            logger.error(f"Error parsing NPD profile HTML: {e}", exc_info=True)
            return None

    @staticmethod
    def _apply_phone_types(phones: List[Dict[str, str]], soup) -> None:
        """
        Fill in "Landline"/"Mobile" from #person-current-phone, matched to
        the JSON-LD-derived numbers already in `phones`. JSON-LD only has
        the bare digits (format_phones hardcodes "type": "unknown"), but the
        rendered card states the type right next to each number.
        """
        heading = soup.select_one("#person-current-phone")
        if not heading:
            return
        container = heading.find_parent()
        if not container:
            return

        types: Dict[str, str] = {}
        for row in container.select(".name-cards-block__text > div"):
            spans = row.find_all("span", recursive=False)
            if len(spans) < 2:
                continue
            number = format_phone(spans[0].get_text(strip=True))
            phone_type = spans[1].get_text(strip=True).strip("()")
            if number and phone_type:
                types[number] = phone_type

        for phone in phones:
            phone_type = types.get(phone.get("number", ""))
            if phone_type:
                phone["type"] = phone_type

    # "Last reported in 2015" next to each previous address
    LAST_REPORTED = re.compile(r'Last reported in (\d{4})')

    @classmethod
    def _apply_address_years(cls, addresses: List[Dict[str, str]], soup) -> None:
        """
        Fill in `yearsActive` from #person-previous-address, matched to the
        JSON-LD-derived addresses already in `addresses` by their normalised
        formatted string -- the DOM comma-separates city/state/zip
        ("Kansas City, MO, 64106") where place_to_address() space-separates
        them ("Kansas City MO 64106"), so commas are stripped before compare.
        """
        heading = soup.select_one("#person-previous-address")
        if not heading:
            return
        container = heading.find_parent()
        if not container:
            return

        years: Dict[str, str] = {}
        for row in container.select(".flex-line"):
            spans = row.find_all("span", recursive=False)
            if len(spans) < 2:
                continue
            match = cls.LAST_REPORTED.match(spans[1].get_text(strip=True))
            if not match:
                continue
            key = cls._normalise_address(spans[0].get_text(strip=True))
            if key:
                years[key] = match.group(1)

        for address in addresses:
            key = cls._normalise_address(address.get("formatted", ""))
            year = years.get(key)
            if year:
                address["yearsActive"] = year

    @staticmethod
    def _normalise_address(text: str) -> str:
        return re.sub(r'\s+', ' ', text.replace(',', '')).strip().lower()

    def _extract_associates(self, soup) -> List[Dict[str, str]]:
        """
        Names under the "Associated" section heading (#person-associated) --
        people NPD links to this person who aren't listed as relatives.
        """
        heading = soup.select_one("#person-associated")
        if not heading:
            return []

        container = heading.find_parent()
        if not container:
            return []

        names: List[Dict[str, str]] = []
        seen = set()
        for a in container.select("a"):
            name = a.get_text(strip=True)
            if name and name not in seen:
                seen.add(name)
                names.append({"name": name})
        return names[: self.MAX_ASSOCIATES]
