#!/usr/bin/env python3
"""
AnyWho HTML Scraper (Cost-Efficient Version)

Uses context.dev HTML method (pattern-based extraction, no AI model).
10x cheaper than Extract API while maintaining data quality.

Cost: ~0.001 per request (vs ~0.005 for Extract)
Performance: ~2-5 seconds per scrape (vs 70-90s for Extract)
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

from targets.anywho.models import ScrapeOutput, SummaryResult, Profile

logger = logging.getLogger(__name__)


@dataclass
class AnyWhoHtmlScraperParams:
    """Parameters for AnyWho HTML scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60


class AnyWhoHtmlScraper:
    """AnyWho scraper using context.dev HTML method (cost-efficient)"""

    BASE_URL = "https://www.anywho.com"

    # State name mapping for AnyWho URL format
    STATE_NAMES = {
        "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
        "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
        "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
        "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
        "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
        "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
        "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
        "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico", "NY": "new-york",
        "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio", "OK": "oklahoma",
        "OR": "oregon", "PA": "pennsylvania", "RI": "rhode-island", "SC": "south-carolina",
        "SD": "south-dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
        "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west-virginia",
        "WI": "wisconsin", "WY": "wyoming"
    }

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not self.api_key:
            raise ValueError("CONTEXT_DEV_API_KEY environment variable not set")
        self.client = ContextDev(api_key=self.api_key, timeout=timeout)

    def _get_state_name(self, state: str) -> str:
        """Convert state abbr to full name for AnyWho URL"""
        state_upper = state.upper()
        return self.STATE_NAMES.get(state_upper, state.lower().replace(" ", "-"))

    def _build_search_url(self, params: AnyWhoHtmlScraperParams) -> str:
        """
        Build AnyWho search URL.

        Pattern: /people/{first}+{last}/{state-name}/{city}
        Example: /people/james+oehring/missouri/cameron
        """
        first = params.firstName.lower()
        last = params.lastName.lower()
        state_name = self._get_state_name(params.state)
        city = params.city.lower().replace(" ", "-")

        return f"{self.BASE_URL}/people/{first}+{last}/{state_name}/{city}"

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

    def _extract_summary_from_html(self, html: str) -> List[SummaryResult]:
        """Extract multiple results from search page HTML using h2-based structure

        Handles AnyWho's data-content attribute pattern for blurred data:
        - Blurred digits (street numbers, phone last4, etc) are in data-content attributes
        - Reconstruct by walking DOM and collecting both text nodes and data-content values
        """
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        try:
            # AnyWho organizes results by h2 tags containing names
            h2_tags = soup.find_all('h2')

            seen_names = set()

            for h2 in h2_tags:
                name = h2.get_text(strip=True)

                # Skip non-name h2 tags (Summary, Numbers, FAQ, etc)
                if not name or name in seen_names or len(name.split()) < 2:
                    continue
                if any(x in name for x in ['Summary', 'Numbers', 'FAQ', 'F.A.Q', 'Filter', 'Area Code', 'Find', 'People']):
                    continue

                # Additional check: name should only contain letters, spaces, hyphens, apostrophes
                if not re.match(r"^[A-Za-z\s\-']+$", name):
                    continue

                seen_names.add(name)

                # Extract data from following h3 sections (Lives in, Phone, Email, etc)
                address = ""
                age_text = ""
                profile_url = ""

                # Find the card container for this person
                card = h2.find_parent(['div', 'section', 'article'])
                if not card:
                    card = h2.find_parent('div')
                    # Go up a few levels to get full card
                    for _ in range(3):
                        if card.find_parent('div'):
                            parent = card.find_parent('div')
                            # Check if parent contains the full record (has multiple h3s)
                            if parent.find_all('h3', limit=3):
                                card = parent

                if card:
                    # Extract data from h3 sections
                    h3_tags = card.find_all('h3')

                    for h3 in h3_tags:
                        label = h3.get_text(strip=True)

                        # Get content after this h3
                        content_elem = h3.find_next(['div', 'p', 'a'])
                        if not content_elem:
                            continue

                        # Reconstruct text with data-content values
                        reconstructed = self._reconstruct_with_data_content(content_elem)

                        if 'Lives in' in label:
                            address = reconstructed[:150]
                        elif 'Phone' in label:
                            # Extract just the first phone
                            phones = [p.strip() for p in reconstructed.split('•')]
                            if phones:
                                # Find phone in extracted text
                                phone_match = re.search(r'\(\d{3}\)\s*\d{3}-\d+', phones[0])
                                if phone_match:
                                    profile_url = ""  # AnyWho doesn't expose phone in summary

                    # Extract age (should be near name)
                    age_span = h2.find_next(string=re.compile(r'Age'))
                    if age_span:
                        age_match = re.search(r'Age\s+(\d{1,3})', str(age_span))
                        if age_match:
                            age_num = int(age_match.group(1))
                            age_text = str(age_num) if age_num < 150 else ""

                    # Find profile URL (View Details button in this card)
                    detail_link = card.find('a', href=re.compile(r'/people/.*?/a\d+'))
                    if detail_link:
                        profile_url = detail_link.get('href', '')

                summary = SummaryResult(
                    resultId=f"anywho_{len(results)}",
                    fullName=name,
                    address=address,
                    ageRange=age_text,
                    profileUrl=profile_url  # type: ignore
                )

                if summary.fullName:
                    results.append(summary)
                    if len(results) >= 5:  # Limit results
                        break

        except Exception as e:
            logger.warning(f"Error extracting summary results: {e}")

        return results

    def _reconstruct_with_data_content(self, element) -> str:
        """Reconstruct text from an element by combining text nodes and data-content attributes"""
        parts = []

        # Walk all children and descendants
        for child in element.descendants:
            if isinstance(child, str):
                text = str(child).strip()
                # Only include meaningful text (not just whitespace)
                if text and len(text) > 0:
                    parts.append(text)
            elif hasattr(child, 'name') and child.name == 'span':
                # Check for data-content attribute (blurred data)
                if 'data-content' in child.attrs:
                    dc = child.get('data-content')
                    parts.append(dc)  # Add unblurred data
                else:
                    # Regular span text
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(text)

        return ' '.join(parts)

    def _parse_age_from_text(self, text: str) -> Optional[int]:
        """Extract age from longer text"""
        if not text:
            return None
        # Look for "Age 61", "Age: 61", etc.
        matches = re.search(r'(?:Age|age)\s*:?\s*(\d{1,3})', text)
        if matches:
            try:
                age = int(matches.group(1))
                return age if age < 150 else None
            except (ValueError, TypeError):
                return None
        return None

    def _extract_profile_from_html(self, html: str, summary: SummaryResult) -> Optional[Profile]:
        """Extract full profile from profile page HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        try:
            profile = Profile(
                profileId=summary.resultId,
                fullName=summary.fullName,
                age=summary.age,
                currentAddress={"formatted": summary.address} if summary.address else {}
            )

            # Extract phone numbers
            phone_text = soup.get_text()
            phone_matches = re.findall(r'\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})', phone_text)
            for match in phone_matches[:3]:
                phone_num = f"({match[0]}) {match[1]}-{match[2]}"
                profile.phoneNumbers.append({
                    "number": phone_num,
                    "type": "primary" if len(profile.phoneNumbers) == 0 else "secondary",
                    "status": "current"
                })

            # Extract email addresses
            email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', phone_text)
            for email in email_matches[:3]:
                if email not in profile.emailAddresses:
                    profile.emailAddresses.append(email.lower())

            # Extract relatives (AnyWho uses familyMembers field)
            rel_section = soup.select_one('[class*="relative"], [class*="family"], [class*="associate"]')
            if rel_section:
                rel_items = rel_section.select('li, div[class*="member"], [class*="person"]')
                for item in rel_items[:10]:
                    text = item.get_text(strip=True)
                    if text and len(text) > 2 and len(text) < 100:
                        profile.familyMembers.append({"name": text, "relationship": "family"})

            return profile if profile.fullName else None

        except Exception as e:
            logger.warning(f"Error extracting profile: {e}")
            return None

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Run AnyWho HTML scraper using context.dev HTML method (cheaper than Extract).

        Args:
            params: Search parameters (firstName, lastName, city, state, timeout)

        Returns:
            ScrapeOutput with results from HTML parsing
        """
        try:
            scraper_params = AnyWhoHtmlScraperParams(**params)

            logger.info(f"AnyWho HTML Scrape started: {scraper_params.firstName} {scraper_params.lastName}")

            start_time = datetime.utcnow()

            # Step 1: Fetch and parse listing page using context.dev HTML method
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching listing (HTML method): {search_url}")

            html_result = self.client.web.web_scrape_html(url=search_url)

            if not html_result or not html_result.html:
                return ScrapeOutput(
                    source="anywho-html",
                    search_params=asdict(scraper_params),
                    summary_results=[],
                    profile=None,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    execution_time_ms=0,
                    status="no_results"
                )

            # Extract multiple summary results from HTML
            summary_results = self._extract_summary_from_html(html_result.html)

            # Step 2: Create profile from first summary (fallback)
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
                source="anywho-html",
                search_params=asdict(scraper_params),
                summary_results=summary_results,
                profile=profile_data,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"AnyWho HTML Scrape completed: {len(summary_results)} results, "
                       f"{execution_time_ms}ms, status={status}")

            return output

        except Exception as e:
            logger.error(f"AnyWho HTML Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="anywho-html",
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
    scraper = AnyWhoHtmlScraper(timeout=params.get("timeout", 60))
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
