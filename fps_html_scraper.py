#!/usr/bin/env python3
"""
FPS HTML Scraper (Cost-Efficient Version)

Uses context.dev HTML method + JSON-LD structured data extraction.
10x cheaper than Extract API while maintaining data quality.

Strategy:
- JSON-LD (Person schema): name, addresses, relatives
- HTML selectors: phone, email (not in JSON-LD)
- Hybrid approach: Best of both worlds

Cost: ~0.001 per request (vs ~0.005 for Extract)
Performance: ~2-5 seconds per scrape (vs 70-90s for Extract)
"""

import os
import sys
import logging
import re
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from bs4 import BeautifulSoup
from context.dev import ContextDev

# targets/ models live alongside this module
sys.path.insert(0, str(Path(__file__).parent))

from targets.fps.models import ScrapeOutput, SummaryResult, Profile

logger = logging.getLogger(__name__)


@dataclass
class FPSHtmlScraperParams:
    """Parameters for FPS HTML scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 10


class FPSHtmlScraper:
    """FPS scraper using context.dev HTML method (cost-efficient)"""

    BASE_URL = "https://www.fastpeoplesearch.com"
    SEARCH_PATH = "/name"

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not self.api_key:
            raise ValueError("CONTEXT_DEV_API_KEY environment variable not set")
        self.client = ContextDev(api_key=self.api_key, timeout=timeout)

    def _build_search_url(self, params: FPSHtmlScraperParams) -> str:
        """
        Build FPS search URL.

        Pattern: /name/{first}-{last}_{city}-{state}
        Example: /name/james-oehring_cameron-mo
        """
        first = params.firstName.lower()
        last = params.lastName.lower()
        city = params.city.lower().replace(" ", "-")
        state = params.state.lower()

        return f"{self.BASE_URL}{self.SEARCH_PATH}/{first}-{last}_{city}-{state}"

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

    def _parse_age_from_text(self, text: str) -> Optional[int]:
        """Extract age from longer text"""
        if not text:
            return None
        # Look for "Age 61", "61 years", etc.
        matches = re.search(r'(?:Age|age)\s*:?\s*(\d{1,3})', text)
        if matches:
            try:
                age = int(matches.group(1))
                return age if age < 150 else None
            except (ValueError, TypeError):
                return None
        return None

    def _extract_jsonld_person(self, html: str) -> Optional[Dict[str, Any]]:
        """Extract Person schema from JSON-LD structured data"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find JSON-LD scripts
        scripts = soup.find_all('script', type='application/ld+json')

        for script in scripts:
            content = script.string
            if not content:
                continue
            try:
                data = json.loads(content)
                # FPS returns array of schemas
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Person':
                            return item
                # Or direct object
                elif isinstance(data, dict) and data.get('@type') == 'Person':
                    return data
            except (json.JSONDecodeError, TypeError):
                continue

        return None

    def _extract_summary_from_html(self, html: str) -> List[SummaryResult]:
        """Extract summary results from search page HTML using BeautifulSoup"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        try:
            # FPS search results - look for card-block divs (actual result cards)
            # Each card contains: h3.card-title > a > span.larger (name) + span.grey (age/location)
            result_cards = soup.select('div.card-block')

            for card in result_cards:
                try:
                    # Extract name from span.larger inside h3
                    name_elem = card.select_one('h3.card-title a span.larger')
                    name = name_elem.get_text(strip=True) if name_elem else None

                    if not name or len(name) < 2:
                        continue

                    # Extract age and location from span.grey (e.g., "Age 61 • Cameron, MO")
                    grey_elem = card.select_one('h3.card-title a span.grey')
                    grey_text = grey_elem.get_text(strip=True) if grey_elem else ""

                    age = None
                    address = ""

                    if grey_text:
                        # Parse "Age 61 • Cameron, MO" format
                        age = self._parse_age_from_text(grey_text)

                        # Extract location (after • separator)
                        if '•' in grey_text:
                            location_part = grey_text.split('•')[1].strip()
                            address = location_part

                    # Prefer the full street address. The address link's visible
                    # text is only "Cameron, MO"; the street sits in the title
                    # attribute ("413 Lovers Ln, Cameron MO 64429"), so reading
                    # link text alone silently drops the house number and street.
                    addr_link = card.select_one('a[href*="/address/"]')
                    if addr_link:
                        street_address = (addr_link.get('title') or '').strip()
                        # Title is prose: "Property Details and People Search for
                        # the address 413 Lovers Ln, Cameron MO 64429"
                        match = re.search(r'address\s+(.+)$', street_address, re.IGNORECASE)
                        if match:
                            address = match.group(1).strip()
                        elif not address:
                            address = addr_link.get_text(strip=True)

                    # Relatives are links under an <h4>Relatives:</h4> heading
                    relatives = ""
                    for heading in card.find_all('h4'):
                        if 'relative' in heading.get_text(strip=True).lower():
                            names = [
                                a.get_text(strip=True)
                                for a in heading.find_parent().find_all('a')
                                if a.get_text(strip=True)
                            ]
                            relatives = ', '.join(names[:5])
                            break

                    # Extract profile URL from the profile link
                    profile_url = ""
                    profile_link = card.select_one('h3.card-title a')
                    if profile_link:
                        profile_url = profile_link.get('href', '')

                    summary = SummaryResult(
                        resultId=f"fps_{len(results)}",
                        fullName=name,
                        address=address,
                        age=age,
                        phone="",
                        profileUrl=profile_url,
                        email="",
                        aliases="",
                        relatives=relatives
                    )

                    results.append(summary)
                    if len(results) >= 5:  # Limit to top 5 results
                        break

                except Exception as e:
                    logger.debug(f"Error parsing individual card: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error extracting summary results: {e}")

        return results

    def _extract_profile_from_html(self, html: str, summary: SummaryResult) -> Optional[Profile]:
        """Extract full profile from HTML using JSON-LD + HTML selectors"""
        soup = BeautifulSoup(html, 'html.parser')

        try:
            # Try to extract from JSON-LD first (more reliable)
            person_data = self._extract_jsonld_person(html)

            if person_data:
                # Extract from JSON-LD
                name = person_data.get('name', summary.fullName)

                # Extract addresses from homeLocation
                current_address = {}
                previous_addresses = []
                home_locations = person_data.get('homeLocation', [])

                if home_locations:
                    for i, loc in enumerate(home_locations):
                        if isinstance(loc, dict):
                            desc = loc.get('description', '').lower()
                            addr_obj = loc.get('address', {})
                            if isinstance(addr_obj, dict):
                                street = addr_obj.get('streetAddress', '')
                                city = addr_obj.get('addressLocality', '')
                                state = addr_obj.get('addressRegion', '')
                                formatted = f"{street}, {city}, {state}".strip()

                                if i == 0 or 'recent' in desc or 'current' in desc:
                                    current_address = {"formatted": formatted} if formatted else {}
                                else:
                                    if formatted:
                                        previous_addresses.append({"formatted": formatted})

                # Extract relatives from JSON-LD
                relatives = []
                related_to = person_data.get('relatedTo', [])
                if isinstance(related_to, list):
                    for rel in related_to:
                        if isinstance(rel, dict) and 'name' in rel:
                            relatives.append({"name": rel['name'], "relationship": "family"})

                profile = Profile(
                    profileId=summary.resultId,
                    fullName=name,
                    currentAddress=current_address,
                    previousAddresses=previous_addresses,
                    relatives=relatives
                )
            else:
                # Fallback to basic summary data
                profile = Profile(
                    profileId=summary.resultId,
                    fullName=summary.fullName,
                    currentAddress={"formatted": summary.address} if summary.address else {}
                )

            # Extract phone/email from HTML (not in JSON-LD)
            page_text = soup.get_text()

            # Extract phone numbers
            phone_matches = re.findall(r'\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})', page_text)
            for match in phone_matches[:3]:
                phone_num = f"({match[0]}) {match[1]}-{match[2]}"
                profile.phoneNumbers.append({
                    "number": phone_num,
                    "type": "primary" if len(profile.phoneNumbers) == 0 else "secondary",
                    "status": "current"
                })

            # Extract email addresses
            email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_text)
            for email in email_matches[:3]:
                if email not in profile.emailAddresses:
                    profile.emailAddresses.append(email.lower())

            return profile if profile.fullName else None

        except Exception as e:
            logger.warning(f"Error extracting profile: {e}")
            return None

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Run FPS HTML scraper using context.dev HTML method (cheaper than Extract).

        Args:
            params: Search parameters (firstName, lastName, city, state, timeout)

        Returns:
            ScrapeOutput with results from HTML parsing
        """
        try:
            scraper_params = FPSHtmlScraperParams(**params)

            logger.info(f"FPS HTML Scrape started: {scraper_params.firstName} {scraper_params.lastName}")

            start_time = datetime.utcnow()

            # Step 1: Fetch and parse listing page using context.dev HTML method
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching listing (HTML method): {search_url}")

            # Use context.dev's cheaper HTML method instead of Extract
            html_result = self.client.web.web_scrape_html(url=search_url)

            if not html_result or not html_result.html:
                return ScrapeOutput(
                    source="fps-html",
                    search_params=asdict(scraper_params),
                    summary_results=[],
                    profile=None,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    execution_time_ms=0,
                    status="no_results"
                )

            # Extract summary results from HTML
            summary_results = self._extract_summary_from_html(html_result.html)

            # Step 2: Try to get profile for first result
            profile_data = None
            if summary_results:
                try:
                    # FPS often requires following a direct profile link
                    # For now, use the summary data as profile fallback
                    profile_data = Profile(
                        profileId=summary_results[0].resultId,
                        fullName=summary_results[0].fullName,
                        currentAddress={"formatted": summary_results[0].address} if summary_results[0].address else {},
                        phoneNumbers=[{"number": summary_results[0].phone, "type": "primary", "status": "current"}] if summary_results[0].phone else []
                    )
                except Exception as e:
                    logger.debug(f"Could not extract profile from summary: {e}")

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            status = "success" if (summary_results or profile_data) else "no_results"

            output = ScrapeOutput(
                source="fps-html",
                search_params=asdict(scraper_params),
                summary_results=summary_results,
                profile=profile_data,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"FPS HTML Scrape completed: {len(summary_results)} results, "
                       f"{execution_time_ms}ms, status={status}")

            return output

        except Exception as e:
            logger.error(f"FPS HTML Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="fps-html",
                search_params=params,
                summary_results=[],
                profile=None,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=0,
                status="failed",
                error=str(e)
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
    scraper = FPSHtmlScraper(timeout=params.get("timeout", 10))
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
    print(f"Results: {len(result['summary_results'])}")
