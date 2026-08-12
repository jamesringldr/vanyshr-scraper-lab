#!/usr/bin/env python3
"""
NPD (National Public Data) HTML Scraper (Cost-Efficient Version)

Uses context.dev HTML method (pattern-based extraction, no AI model).
Leverages JSON-LD structured data for robust extraction.

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

# Add lab to path for models
sys.path.insert(0, str(Path(__file__).parent.parent / "vanyshr-scraper-lab"))

from targets.npd.models import ScrapeOutput, SummaryResult, Profile

logger = logging.getLogger(__name__)


@dataclass
class NPDHtmlScraperParams:
    """Parameters for NPD HTML scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60


class NPDHtmlScraper:
    """NPD scraper using context.dev HTML method (cost-efficient)"""

    BASE_URL = "https://www.nationalpublicdata.com"

    # State abbreviation mapping
    STATE_ABBR = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
        "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
        "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
        "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
        "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
        "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
        "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
        "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
        "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
        "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
        "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
        "wisconsin": "WI", "wyoming": "WY"
    }

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not self.api_key:
            raise ValueError("CONTEXT_DEV_API_KEY environment variable not set")
        self.client = ContextDev(api_key=self.api_key, timeout=timeout)

    def _get_state_abbr(self, state: str) -> str:
        """Convert state name or abbr to standard 2-letter abbr"""
        state_lower = state.lower()
        if len(state_lower) == 2:
            return state_lower.upper()
        return self.STATE_ABBR.get(state_lower, state.upper()[:2])

    def _build_search_url(self, params: NPDHtmlScraperParams) -> str:
        """
        Build NPD search URL.

        Pattern: /people/{letter}/{first}-{last}/{state-abbr}/{city}
        Example: /people/O/James-Oehring/MO/Cameron
        """
        first = params.firstName.capitalize()
        last = params.lastName.capitalize()
        state_abbr = self._get_state_abbr(params.state)
        city = params.city.capitalize()
        letter = last[0].upper()

        return f"{self.BASE_URL}/people/{letter}/{first}-{last}/{state_abbr}/{city}"

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
                if data.get('@type') == 'Person':
                    return data
            except (json.JSONDecodeError, TypeError):
                continue

        return None

    def _extract_summary_from_html(self, html: str) -> List[SummaryResult]:
        """Extract multiple result cards from NPD search page HTML

        NPD search results display as h2 tags with pattern: "Name, Age City, State"
        Each result card is wrapped in a parent div with class 'name-cards-head'
        """
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        try:
            # Find all h2 tags
            h2_tags = soup.find_all('h2')

            for h2 in h2_tags:
                # Check if this h2 is a result card (has name-cards-head parent)
                parent = h2.find_parent(class_='name-cards-head')
                if not parent:
                    continue  # Skip non-result h2s (FAQ, Background Report, etc)

                # Parse the h2 text: "Name, Age City, State"
                h2_text = h2.get_text(strip=True)

                # Extract name, age, location using regex
                # Pattern: "FirstName LastName, NN City, State"
                match = re.match(r'([A-Za-z\s]+),\s*(\d+)([A-Za-z\s,]+)', h2_text)
                if not match:
                    continue

                name = match.group(1).strip()
                age_str = match.group(2)
                location = match.group(3).strip()

                # Parse age
                try:
                    age = int(age_str)
                except (ValueError, TypeError):
                    age = None

                # Find profile URL (link within or after h2)
                profile_url = ""
                link = h2.find_next('a', href=re.compile(r'/people/'))
                if link:
                    profile_url = link.get('href', '')

                # Create summary result
                summary = SummaryResult(
                    resultId=f"npd_{len(results)}",
                    fullName=name,
                    address=location,  # "City, State" from parsed text
                    ageRange=str(age) if age else "",
                    age=age,
                    profileUrl=profile_url  # type: ignore
                )

                results.append(summary)

                # Limit to 5 results
                if len(results) >= 5:
                    break

        except Exception as e:
            logger.warning(f"Error extracting summary results: {e}")

        return results

    def _parse_age_from_text(self, text: str) -> Optional[int]:
        """Extract age from longer text"""
        if not text:
            return None
        # Look for "Age 61", "DOB", etc.
        matches = re.search(r'(?:Age|age)\s*:?\s*(\d{1,3})', text)
        if matches:
            try:
                age = int(matches.group(1))
                return age if age < 150 else None
            except (ValueError, TypeError):
                return None
        # Try to extract from DOB if present
        dob_matches = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
        if dob_matches:
            try:
                year = int(dob_matches.group(3))
                current_year = datetime.now().year
                age = current_year - year
                return age if 0 < age < 150 else None
            except (ValueError, TypeError):
                return None
        return None

    def _extract_profile_from_html(self, html: str, summary: SummaryResult) -> Optional[Profile]:
        """Extract full profile from NPD HTML using JSON-LD structured data"""

        try:
            person_data = self._extract_jsonld_person(html)

            if not person_data:
                # Fallback to summary data
                return Profile(
                    profileId=summary.resultId,
                    fullName=summary.fullName,
                    age=summary.age,
                    currentAddress={"formatted": summary.address} if summary.address else {}
                )

            name = person_data.get('name', summary.fullName)

            # Extract current address
            home_locations = person_data.get('HomeLocation', [])
            current_address = {}
            if home_locations and isinstance(home_locations[0], dict):
                addr = home_locations[0].get('address', {})
                if isinstance(addr, dict):
                    street = addr.get('streetAddress', '')
                    city = addr.get('addressLocality', '')
                    state = addr.get('addressRegion', '')
                    zip_code = addr.get('postalCode', '')
                    formatted = f"{street}, {city}, {state} {zip_code}".strip()
                    current_address = {"formatted": formatted}

            # Extract previous addresses
            previous_addresses = []
            if len(home_locations) > 1:
                for loc in home_locations[1:]:
                    if isinstance(loc, dict):
                        addr = loc.get('address', {})
                        if isinstance(addr, dict):
                            street = addr.get('streetAddress', '')
                            city = addr.get('addressLocality', '')
                            state = addr.get('addressRegion', '')
                            zip_code = addr.get('postalCode', '')
                            formatted = f"{street}, {city}, {state} {zip_code}".strip()
                            if formatted:
                                previous_addresses.append({"formatted": formatted})

            # Extract age from birthDate
            birth_date = person_data.get('birthDate')
            age = None
            if birth_date:
                try:
                    birth_year = int(birth_date)
                    age = datetime.now().year - birth_year
                except (ValueError, TypeError):
                    pass

            # Extract phone numbers from JSON-LD
            phones_data = person_data.get('telephone', [])
            phone_numbers = []
            for i, phone in enumerate(phones_data[:3]):
                # Format phone (remove non-digits then format)
                digits = re.sub(r'\D', '', str(phone))
                if len(digits) == 10:
                    formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                else:
                    formatted = phone
                phone_numbers.append({
                    "number": formatted,
                    "type": "primary" if i == 0 else "secondary",
                    "status": "current"
                })

            # Extract emails from JSON-LD
            email_addresses = person_data.get('email', [])
            email_addresses = [e.lower() for e in email_addresses if isinstance(e, str)][:5]

            # Extract relatives from JSON-LD
            relatives = []
            related_to = person_data.get('relatedTo', [])
            if isinstance(related_to, list):
                for rel in related_to:
                    if isinstance(rel, dict) and 'name' in rel:
                        relatives.append({"name": rel['name'], "relationship": "family"})
            elif isinstance(related_to, dict) and 'name' in related_to:
                relatives.append({"name": related_to['name'], "relationship": "family"})

            profile = Profile(
                profileId=summary.resultId,
                fullName=name,
                age=age,
                currentAddress=current_address,
                previousAddresses=previous_addresses,
                phoneNumbers=phone_numbers,
                emailAddresses=email_addresses,
                relatives=relatives
            )

            return profile if profile.fullName else None

        except Exception as e:
            logger.warning(f"Error extracting profile: {e}")
            return None

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Run NPD HTML scraper using context.dev HTML method (cheaper than Extract).

        Args:
            params: Search parameters (firstName, lastName, city, state, timeout)

        Returns:
            ScrapeOutput with results from HTML parsing
        """
        try:
            scraper_params = NPDHtmlScraperParams(**params)

            logger.info(f"NPD HTML Scrape started: {scraper_params.firstName} {scraper_params.lastName}")

            start_time = datetime.utcnow()

            # Step 1: Fetch and parse listing page using context.dev HTML method
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching listing (HTML method): {search_url}")

            html_result = self.client.web.web_scrape_html(url=search_url)

            if not html_result or not html_result.html:
                return ScrapeOutput(
                    source="npd-html",
                    search_params=asdict(scraper_params),
                    summary_results=[],
                    profile=None,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    execution_time_ms=0,
                    status="no_results"
                )

            # Extract summary results from HTML
            summary_results = self._extract_summary_from_html(html_result.html)

            # Step 2: Create profile from first summary
            profile_data = None
            if summary_results:
                try:
                    profile_data = Profile(
                        profileId=summary_results[0].resultId,
                        fullName=summary_results[0].fullName,
                        age=summary_results[0].age,
                        currentAddress={"formatted": summary_results[0].address} if summary_results[0].address else {}
                    )
                except Exception as e:
                    logger.debug(f"Could not create profile from summary: {e}")

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            status = "success" if (summary_results or profile_data) else "no_results"

            output = ScrapeOutput(
                source="npd-html",
                search_params=asdict(scraper_params),
                summary_results=summary_results,
                profile=profile_data,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"NPD HTML Scrape completed: {len(summary_results)} results, "
                       f"{execution_time_ms}ms, status={status}")

            return output

        except Exception as e:
            logger.error(f"NPD HTML Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="npd-html",
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
    scraper = NPDHtmlScraper(timeout=params.get("timeout", 60))
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
