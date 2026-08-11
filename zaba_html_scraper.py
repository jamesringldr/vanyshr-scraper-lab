#!/usr/bin/env python3
"""
Zaba Search HTML Scraper (Residential IP Required)

⚠️ CRITICAL: Zaba blocks all datacenter/API access (including context.dev Extract AND HTML method).
This scraper is IMPLEMENTATION-READY but REQUIRES FALLBACK to residential IP service.

BLOCKING ISSUE:
- Zaba detects datacenter IPs and returns WEBSITE_ACCESS_ERROR: 400
- Affects both Extract API and HTML method
- NO configuration on context.dev side can fix this

SOLUTION: Use serv01:8788 residential IP service (already configured in prod)
- Direct curl/requests through residential Windows service
- See vanyshr-mono for serv01:8788 integration pattern
- Alternative: Use Extract-based scraper as fallback when HTML fails

This file provides:
✅ Correct URL pattern for Zaba searches
✅ HTML parsing logic for multi-profile results
✅ Structured error handling and fallback triggers
❌ Does NOT work with context.dev (Zaba blocks it)

Deployment note: Integrate with sequence runner to fallback to serv01:8788 when
context.dev fails with WEBSITE_ACCESS_ERROR.
"""

import os
import sys
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from bs4 import BeautifulSoup
from context.dev import ContextDev

# Add lab to path for models
sys.path.insert(0, str(Path(__file__).parent.parent / "vanyshr-scraper-lab"))

from targets.zaba.models import ScrapeOutput, Profile

logger = logging.getLogger(__name__)


@dataclass
class ZabaHtmlScraperParams:
    """Parameters for Zaba HTML scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60


class ZabaHtmlScraper:
    """Zaba scraper using context.dev HTML method (cost-efficient)"""

    BASE_URL = "https://search.zaba.com"
    SEARCH_PATH = "/s"

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not self.api_key:
            raise ValueError("CONTEXT_DEV_API_KEY environment variable not set")
        self.client = ContextDev(api_key=self.api_key, timeout=timeout)

    def _build_search_url(self, params: ZabaHtmlScraperParams) -> str:
        """
        Build Zaba search URL with query parameters.

        Pattern: /s?q={first}+{last}&where={city},+{state}
        Example: /s?q=james+oehring&where=cameron,+mo
        """
        first = params.firstName
        last = params.lastName
        city = params.city
        state = params.state.lower()

        query = f"{first}+{last}".replace(" ", "+")
        where = f"{city},+{state}".replace(" ", "+")

        return f"{self.BASE_URL}{self.SEARCH_PATH}?q={query}&where={where}"

    def _parse_age(self, age_str: Optional[str]) -> Optional[int]:
        """Parse age string to int"""
        if not age_str:
            return None
        try:
            digits = re.findall(r'\d+', str(age_str))
            if digits:
                first_num = int(digits[0])
                if first_num < 150:
                    return first_num
            return None
        except (ValueError, TypeError):
            return None

    def _extract_age_from_text(self, text: str) -> Optional[int]:
        """Extract age from text"""
        if not text:
            return None
        # Look for various age formats
        matches = re.search(r'(?:Age|age)\s*:?\s*(\d{1,3})', text)
        if matches:
            try:
                age = int(matches.group(1))
                return age if age < 150 else None
            except (ValueError, TypeError):
                return None
        return None

    def _extract_profiles_from_html(self, html: str) -> List[Profile]:
        """
        Extract multiple profiles from Zaba search results.

        Zaba returns 2-20 results for a single query, unlike other brokers
        that return just one primary match.
        """
        soup = BeautifulSoup(html, 'html.parser')
        profiles = []

        try:
            # Zaba results - look for result cards/rows
            result_cards = soup.select(
                'div[class*="result"], div[class*="person"], '
                'tr[class*="result"], li[class*="person"]'
            )

            seen_names = set()

            for i, card in enumerate(result_cards):
                # Extract name
                name_elem = card.select_one('h2, h3, .name, .person-name, a[class*="name"]')
                if not name_elem:
                    name_elem = card.select_one('a')
                name = name_elem.get_text(strip=True) if name_elem else None

                if not name or name in seen_names or len(name) < 2:
                    continue

                seen_names.add(name)

                # Extract address
                addr_elem = card.select_one('[class*="address"], .location, .city-state')
                address = addr_elem.get_text(strip=True) if addr_elem else ""

                # Extract age
                card_text = card.get_text()
                age = self._extract_age_from_text(card_text)

                # Extract phone if present
                phone_text = card_text
                phone_matches = re.findall(r'\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})', phone_text)
                phones = []
                for match in phone_matches[:2]:
                    phone_num = f"({match[0]}) {match[1]}-{match[2]}"
                    phones.append({
                        "number": phone_num,
                        "type": "primary" if len(phones) == 0 else "secondary",
                        "status": "current"
                    })

                # Extract email if present
                email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', phone_text)
                emails = [e.lower() for e in email_matches[:2]]

                profile = Profile(
                    profileId=f"zaba_{len(profiles)}",
                    fullName=name,
                    age=age,
                    currentAddress={"formatted": address} if address else {},
                    phoneNumbers=phones,
                    emailAddresses=emails
                )

                if profile.fullName:
                    profiles.append(profile)
                    if len(profiles) >= 20:  # Zaba can return up to 20+ results
                        break

        except Exception as e:
            logger.warning(f"Error extracting profiles: {e}")

        return profiles

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Run Zaba HTML scraper using context.dev HTML method (cheaper than Extract).

        Args:
            params: Search parameters (firstName, lastName, city, state, timeout)

        Returns:
            ScrapeOutput with multiple profiles
        """
        try:
            scraper_params = ZabaHtmlScraperParams(**params)

            logger.info(f"Zaba HTML Scrape started: {scraper_params.firstName} {scraper_params.lastName}")

            start_time = datetime.utcnow()

            # Fetch search page using context.dev HTML method
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching search (HTML method): {search_url}")

            html_result = self.client.web.web_scrape_html(url=search_url)

            if not html_result or not html_result.html:
                return ScrapeOutput(
                    source="zaba-html",
                    search_params=asdict(scraper_params),
                    profiles=[],
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    execution_time_ms=0,
                    status="no_results"
                )

            # Extract all profiles from HTML
            profiles = self._extract_profiles_from_html(html_result.html)

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            status = "success" if profiles else "no_results"

            output = ScrapeOutput(
                source="zaba-html",
                search_params=asdict(scraper_params),
                profiles=profiles,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"Zaba HTML Scrape completed: {len(profiles)} profiles, "
                       f"{execution_time_ms}ms, status={status}")

            return output

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Zaba HTML Scrape failed: {error_msg}", exc_info=True)

            # Provide helpful feedback for IP blocking
            if "WEBSITE_ACCESS_ERROR" in error_msg or "400" in error_msg:
                error_msg = (
                    "Zaba blocks datacenter IPs (context.dev not accessible). "
                    "Use residential IP fallback: serv01:8788 service"
                )

            return ScrapeOutput(
                source="zaba-html",
                search_params=params,
                profiles=[],
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=0,
                status="failed",
                error=error_msg
            )


# Standard interface
def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard entry point for scraper sequences.

    Args:
        params: {firstName, lastName, city, state, timeout}

    Returns:
        Dictionary matching ScrapeOutput schema
    """
    scraper = ZabaHtmlScraper(timeout=params.get("timeout", 60))
    output = scraper.run(params)
    return asdict(output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test
    result = run({
        "firstName": "James",
        "lastName": "Oehring",
        "city": "Cameron",
        "state": "MO"
    })

    print(f"Status: {result['status']}")
    print(f"Time: {result['execution_time_ms']}ms")
    print(f"Results: {len(result['profiles'])}")
