#!/usr/bin/env python3
"""
FPS HTML Scraper (Cost-Efficient Version)

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

    def _extract_summary_from_html(self, html: str) -> List[SummaryResult]:
        """Extract summary results from search page HTML using BeautifulSoup"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        try:
            # FPS search results - look for person cards/rows
            # Try multiple selectors to be robust to page changes
            result_cards = soup.select(
                'div[class*="result"], div[class*="person"], '
                'a[href*="/name/"], div[data-testid*="result"]'
            )

            # Deduplicate by extracting unique result sections
            seen_names = set()

            for card in result_cards:
                # Extract name
                name_elem = card.select_one('h2, h3, .name, [class*="name"]')
                if not name_elem:
                    name_elem = card
                name = name_elem.get_text(strip=True) if name_elem else None

                if not name or name in seen_names:
                    continue

                seen_names.add(name)

                # Extract address/location
                addr_elem = card.select_one('[class*="address"], .location, [class*="city"]')
                address = addr_elem.get_text(strip=True) if addr_elem else ""

                # Extract age if present
                age_text = card.get_text()
                age = self._parse_age_from_text(age_text)

                summary = SummaryResult(
                    resultId=f"fps_{len(results)}",
                    fullName=name,
                    address=address,
                    age=age
                )

                if summary.fullName:
                    results.append(summary)
                    if len(results) >= 5:  # Limit to top 5 results
                        break

        except Exception as e:
            logger.warning(f"Error extracting summary results: {e}")

        return results

    def _extract_profile_from_html(self, html: str, summary: SummaryResult) -> Optional[Profile]:
        """Extract full profile from profile page HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        try:
            profile = Profile(
                profileId=summary.resultId,
                fullName=summary.fullName,
                currentAddress={"formatted": summary.address} if summary.address else {}
            )

            # Extract phone numbers using flexible selectors
            phone_text = soup.get_text()
            phone_matches = re.findall(r'\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})', phone_text)
            for match in phone_matches[:3]:  # Limit to 3 phones
                phone_num = f"({match[0]}) {match[1]}-{match[2]}"
                profile.phoneNumbers.append({
                    "number": phone_num,
                    "type": "primary" if len(profile.phoneNumbers) == 0 else "secondary",
                    "status": "current"
                })

            # Extract email addresses
            email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', phone_text)
            for email in email_matches[:3]:  # Limit to 3 emails
                if email not in profile.emailAddresses:
                    profile.emailAddresses.append(email.lower())

            # Extract relatives from family section
            rel_section = soup.select_one('[class*="relative"], [class*="family"], [class*="associate"]')
            if rel_section:
                rel_items = rel_section.select('li, div[class*="member"], [class*="person"]')
                for item in rel_items[:10]:
                    text = item.get_text(strip=True)
                    if text and len(text) > 2 and len(text) < 100:
                        profile.relatives.append({"name": text, "relationship": "family"})

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
