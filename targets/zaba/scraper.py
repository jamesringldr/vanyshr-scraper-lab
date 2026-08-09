# targets/zaba/scraper.py
"""
Zaba Scraper

Pluggable scraper module for vanyshr-mono app.
Standard interface: scraper.run(params) -> Output

Note: Zaba returns all results on a single page (no separate profile pages).
All results are full profiles displayed as blocks on the same page.
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict

from .parser import ZabaParser
from .models import ScrapeOutput, Profile

logger = logging.getLogger(__name__)


@dataclass
class ScraperParams:
    """Input parameters for Zaba scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 10


class ZabaScraper:
    """Zaba scraper implementation"""

    BASE_URL = "https://search.zaba.com"
    SEARCH_PATH = "/s"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.parser = ZabaParser()
        self.session = None

    async def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Main entry point for scraping Zaba.

        Args:
            params: Dictionary with keys: firstName, lastName, city, state, [timeout]

        Returns:
            ScrapeOutput with multiple full profiles (no summary/profile split)
        """
        try:
            # Validate and normalize params
            scraper_params = ScraperParams(**params)

            logger.info(f"Zaba Scrape started: {scraper_params.firstName} {scraper_params.lastName}, "
                       f"{scraper_params.city}, {scraper_params.state}")

            start_time = datetime.utcnow()

            # Scrape all profiles from single page
            profiles = await self._scrape_profiles(scraper_params)

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            output = ScrapeOutput(
                source="zaba",
                search_params=asdict(scraper_params),
                summary_results=[],  # No summary page for Zaba
                profiles=profiles,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status="success" if profiles else "no_results"
            )

            logger.info(f"Zaba Scrape completed: {len(profiles)} profiles, "
                       f"{execution_time_ms}ms")

            return output

        except Exception as e:
            logger.error(f"Zaba Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="zaba",
                search_params=params,
                summary_results=[],
                profiles=[],
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=0,
                status="failed",
                error=str(e)
            )

    async def _scrape_profiles(self, params: ScraperParams) -> List[Profile]:
        """Scrape all profiles from single search page"""
        # TODO: Implement HTTP request to Zaba search page
        # Use self.parser.parse_profiles_html() to extract all result blocks
        # Each result block is a complete profile
        pass


# Standard interface for vanyshr-mono integration
async def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard entry point for vanyshr-mono scraper sequences.

    This function is imported and called by:
    - QuickScan workflow (returns all profiles found)
    - Subscriber monitoring workflow (returns all profiles found)

    Args:
        params: {firstName, lastName, city, state, timeout}

    Returns:
        Dictionary matching ScrapeOutput schema (JSON-serializable)
    """
    scraper = ZabaScraper(timeout=params.get("timeout", 10))
    output = await scraper.run(params)
    return asdict(output)

