# targets/leakcheck/scraper.py
"""
LeakCheck Email Breach Lookup Scraper

Pluggable scraper module for vanyshr-mono app.
Checks if an email has been found in known data breaches via LeakCheck API.

Standard interface: scraper.run(params) -> Output
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import httpx

from .parser import LeakCheckParser
from .models import ScrapeOutput

logger = logging.getLogger(__name__)


@dataclass
class ScraperParams:
    """Input parameters for LeakCheck scraper"""
    email: str
    timeout: int = 10


class LeakCheckScraper:
    """LeakCheck breach lookup scraper implementation"""

    BASE_URL = "https://leakcheck.io/api/public"
    USER_AGENT = "VanyshrApp/1.0 (Email Breach Lookup)"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.parser = LeakCheckParser()

    async def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Main entry point for LeakCheck breach lookup.

        Args:
            params: Dictionary with keys: email, [timeout]

        Returns:
            ScrapeOutput with breach data for email
        """
        try:
            # Validate and normalize params
            scraper_params = ScraperParams(**params)

            logger.info(f"LeakCheck Lookup started: {scraper_params.email}")

            start_time = datetime.utcnow()

            # Query LeakCheck API
            breaches = await self._query_leakcheck(scraper_params)

            # Summarize
            summary = self._summarize_results(breaches)

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            output = ScrapeOutput(
                source="leakcheck",
                search_params={'email': scraper_params.email},
                breaches=breaches,
                summary=summary,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status="success" if breaches else "not_found"
            )

            logger.info(f"LeakCheck Lookup completed: {summary['totalBreaches']} breaches, "
                       f"{execution_time_ms}ms")

            return output

        except Exception as e:
            logger.error(f"LeakCheck Lookup failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="leakcheck",
                search_params=params,
                breaches=[],
                summary={},
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=0,
                status="failed",
                error=str(e)
            )

    async def _query_leakcheck(self, params: ScraperParams) -> List[Dict[str, Any]]:
        """Query LeakCheck API for breaches"""
        try:
            async with httpx.AsyncClient(timeout=params.timeout) as client:
                # Build request with correct parameters
                url = self.BASE_URL
                query_params = {
                    'check': params.email,  # Email to check
                    'type': 'email'          # Type of check
                }
                headers = {'User-Agent': self.USER_AGENT}

                logger.debug(f"Querying LeakCheck: {url} with email={params.email}")

                # Make request
                response = await client.get(url, params=query_params, headers=headers)

                # Check response status
                if response.status_code == 429:
                    logger.warning("LeakCheck API rate limited")
                    return []

                if response.status_code == 404:
                    logger.info(f"Email not found in LeakCheck: {params.email}")
                    return []

                if response.status_code != 200:
                    logger.error(f"LeakCheck API error: {response.status_code}")
                    return []

                # Parse response
                try:
                    data = response.json()
                    breaches = self.parser.parse_api_response(data)
                    return breaches
                except Exception as e:
                    logger.error(f"Error parsing LeakCheck response: {str(e)}")
                    return []

        except httpx.TimeoutException:
            logger.error(f"LeakCheck request timeout after {params.timeout}s")
            return []
        except Exception as e:
            logger.error(f"Error querying LeakCheck: {str(e)}")
            return []

    def _summarize_results(self, breaches: List[Dict]) -> Dict[str, Any]:
        """Summarize breach results"""
        total_compromised = 0
        for breach in breaches:
            total_compromised += breach.get('compromised_count', 0)

        return {
            'totalBreaches': len(breaches),
            'isCompromised': len(breaches) > 0,
            'compromised_records': total_compromised,
        }


# Standard interface for vanyshr-mono integration
async def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard entry point for vanyshr-mono scraper sequences.

    This function is imported and called by:
    - QuickScan workflow (breach lookup)
    - Subscriber monitoring workflow (continuous monitoring)

    Args:
        params: {email, timeout}

    Returns:
        Dictionary matching ScrapeOutput schema (JSON-serializable)
    """
    scraper = LeakCheckScraper(timeout=params.get("timeout", 10))
    output = await scraper.run(params)
    return asdict(output)

