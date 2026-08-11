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

logger = logging.getLogger(__name__)


class FPSFullProfileScraper:
    """Scrapes full profiles from FastPeopleSearch using context.dev HTML method"""

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
        """Parse full profile HTML and extract data"""
        soup = BeautifulSoup(html, "html.parser")

        try:
            profile = Profile(profileId=profile_id)

            # Extract name - use same pattern as summary scraper (h3.card-title a span.larger)
            name_elem = soup.select_one("h3.card-title a span.larger, h1, .profile-name")
            if name_elem:
                full_text = name_elem.get_text(strip=True)
                # Clean up: extract just the name part (before location info)
                # The element might contain name + city info concatenated
                # Try to find where the name ends (usually stops before " in " with word boundary)
                import re as regex
                # Match: FirstName LastName (stops at location separators)
                name_match = regex.match(r'^([A-Za-z\s\-\.\']+?)(?:\s*[,(]|\s+in\s+)', full_text)
                if name_match:
                    profile.fullName = name_match.group(1).strip()
                else:
                    # Fallback: split on common separators
                    for sep in ['(', ',']:
                        if sep in full_text:
                            full_text = full_text.split(sep)[0].strip()
                    profile.fullName = full_text

            # Extract age
            age_text = soup.get_text()
            age_match = re.search(r"Age\s+(\d+)", age_text)
            if age_match:
                profile.age = int(age_match.group(1))

            # Extract emails
            emails = self._extract_emails(html)
            profile.emailAddresses = list(emails)

            # Extract phone numbers
            phones = self._extract_phones(html)
            for phone in phones:
                profile.phoneNumbers.append({"number": phone, "type": "unknown"})

            # Extract addresses
            profile.currentAddress, profile.previousAddresses = self._extract_addresses(
                soup
            )

            # Extract relatives
            profile.relatives = self._extract_relatives(soup)

            # Extract associates
            profile.associates = self._extract_associates(soup)

            # Extract properties
            profile.properties = self._extract_properties(soup)

            logger.debug(
                f"Parsed profile: {profile.fullName}, "
                f"{len(profile.emailAddresses)} emails, "
                f"{len(profile.phoneNumbers)} phones"
            )

            return profile if profile.fullName else None

        except Exception as e:
            logger.error(f"Error parsing profile HTML: {e}", exc_info=True)
            return None

    def _extract_emails(self, html: str) -> set:
        """Extract email addresses from HTML"""
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = set(re.findall(email_pattern, html.lower()))

        # Filter out system/service emails
        system_domains = {
            'fastpeoplesearch.com',
            'support@',
            'noreply@',
            'no-reply@',
            'admin@',
            'info@',
            'notifications@',
        }

        filtered = set()
        for email in emails:
            # Skip if it's a system email
            if any(domain in email for domain in system_domains):
                continue
            filtered.add(email)

        return filtered

    def _extract_phones(self, html: str) -> List[str]:
        """Extract phone numbers from HTML"""
        # US phone number patterns: (123) 456-7890, 123-456-7890, 1234567890
        phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        matches = re.findall(phone_pattern, html)

        phones = []
        seen = set()

        for match in matches:
            # Normalize: remove all non-digits, then format as (XXX) XXX-XXXX
            digits = re.sub(r"\D", "", match)
            if len(digits) == 10 and digits not in seen:
                formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                phones.append(formatted)
                seen.add(digits)

        return phones[:3]  # Limit to top 3

    def _extract_addresses(
        self, soup: BeautifulSoup
    ) -> tuple[Dict[str, str], List[Dict[str, str]]]:
        """Extract current and previous addresses"""
        current_address = {}
        previous_addresses = []

        # Look for "Current Address" and "Past Addresses" sections
        # Try multiple selectors to handle page structure variations
        address_links = soup.select('a[href*="/address/"], [class*="address"] a')

        if not address_links:
            # Fallback: look for any divs with address-like content
            address_sections = soup.select('[class*="address"], [class*="location"]')
        else:
            address_sections = address_links

        for i, section in enumerate(address_sections[:5]):  # Limit to 5 addresses
            if isinstance(section, str):
                addr_text = section
            else:
                addr_text = section.get_text(strip=True)

            if not addr_text or len(addr_text) < 5:
                continue

            addr_dict = {"formatted": addr_text}

            if i == 0:
                current_address = addr_dict
            else:
                previous_addresses.append(addr_dict)

        return current_address, previous_addresses

    def _extract_relatives(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract relatives from profile"""
        relatives = []

        # Look for relatives section
        rel_header = soup.find(string=re.compile(r"Relatives?", re.I))
        if rel_header:
            # Find parent container with list
            container = rel_header.find_parent("div")
            if container:
                # Extract names from list items
                for li in container.select("li, [class*='relative']"):
                    name = li.get_text(strip=True)
                    if name and len(name) > 2:
                        relatives.append({"name": name, "relationship": "family"})

        return relatives[:5]  # Limit to 5

    def _extract_associates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract associates/neighbors from profile"""
        associates = []

        # Look for associates section
        assoc_header = soup.find(string=re.compile(r"Associates?|Neighbors?", re.I))
        if assoc_header:
            # Find parent container
            container = assoc_header.find_parent("div")
            if container:
                # Extract names
                for li in container.select("li, [class*='associate']"):
                    name = li.get_text(strip=True)
                    if name and len(name) > 2:
                        associates.append({"name": name})

        return associates[:5]  # Limit to 5

    def _extract_properties(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract properties (real estate) from profile"""
        properties = []

        # Look for property section
        prop_header = soup.find(string=re.compile(r"Properties?|Real Estate", re.I))
        if prop_header:
            # Find parent container
            container = prop_header.find_parent("div")
            if container:
                # Extract property addresses
                for prop in container.select("[class*='property'], li"):
                    prop_text = prop.get_text(strip=True)
                    if prop_text and len(prop_text) > 10:
                        properties.append({"address": prop_text})

        return properties[:5]  # Limit to 5


def main():
    """Test full profile scraper"""
    import os

    api_key = os.getenv("CONTEXT_DEV_API_KEY")
    if not api_key:
        print("❌ CONTEXT_DEV_API_KEY not set")
        return

    scraper = FPSFullProfileScraper(api_key=api_key)

    # Test with a profile URL (from Phase 1 results)
    profile_url = "/james-oehring_id_G3697305023830937972"

    profile = scraper.scrape_profile(profile_url)

    if profile:
        print(f"✅ Profile scraped: {profile.fullName}")
        print(f"   Age: {profile.age}")
        print(f"   Emails: {profile.emailAddresses}")
        print(f"   Phones: {[p['number'] for p in profile.phoneNumbers]}")
        print(f"   Current Address: {profile.currentAddress}")
        print(f"   Relatives: {len(profile.relatives)}")
    else:
        print("❌ Failed to scrape profile")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
