# targets/hudson-rock/username/scraper.py
"""
Hudson Rock Username Search Scraper

Searches infostealer databases for credentials associated with usernames.

Standard interface: scraper.run(params) -> Output
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import httpx

from .parser import HudsonRockUsernameParser
from .models import ScrapeOutput

logger = logging.getLogger(__name__)


@dataclass
class ScraperParams:
    """Input parameters for Hudson Rock username scraper"""
    username: str
    apiKey: str
    timeout: int = 30


class HudsonRockUsernameScraper:
    """Hudson Rock username search scraper implementation"""

    BASE_URL = "https://api.hudsonrock.com/json/v3"
    ENDPOINT = "/search-by-login-usernames"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.parser = HudsonRockUsernameParser()

    async def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Main entry point for Hudson Rock username search.

        Args:
            params: Dictionary with keys: username, apiKey, [timeout]

        Returns:
            ScrapeOutput with stealer and credential data
        """
        try:
            # Validate and normalize params
            scraper_params = ScraperParams(**params)

            logger.info(f"Hudson Rock Username Search started: {scraper_params.username}")

            start_time = datetime.utcnow()

            # Query Hudson Rock API
            stealers = await self._query_api(scraper_params)

            # Summarize
            summary = self._summarize_results(stealers)

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            output = ScrapeOutput(
                source="hudson-rock-username",
                search_params={'username': scraper_params.username},
                breaches=stealers,
                summary=summary,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status="success" if stealers else "not_found"
            )

            logger.info(f"Hudson Rock Username Search completed: {summary['total_stealers']} stealers, "
                       f"{execution_time_ms}ms")

            return output

        except Exception as e:
            logger.error(f"Hudson Rock Username Search failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="hudson-rock-username",
                search_params=params,
                breaches=[],
                summary={},
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=0,
                status="failed",
                error=str(e)
            )

    async def _query_api(self, params: ScraperParams) -> List[Dict[str, Any]]:
        """Query Hudson Rock API for username"""
        try:
            async with httpx.AsyncClient(timeout=params.timeout) as client:
                url = f"{self.BASE_URL}{self.ENDPOINT}"
                headers = {'api-key': params.apiKey}
                payload = {'username': params.username}

                logger.debug(f"Querying Hudson Rock: {url} with username={params.username}")

                response = await client.post(url, json=payload, headers=headers)

                # Check response status
                if response.status_code == 429:
                    logger.warning("Hudson Rock API rate limited")
                    return []

                if response.status_code == 401:
                    logger.error("Hudson Rock API authentication failed")
                    return []

                if response.status_code == 404:
                    logger.info(f"Username not found in Hudson Rock: {params.username}")
                    return []

                if response.status_code != 200:
                    logger.error(f"Hudson Rock API error: {response.status_code}")
                    return []

                # Parse response
                try:
                    data = response.json()
                    stealers = self.parser.parse_api_response(data)
                    return stealers
                except Exception as e:
                    logger.error(f"Error parsing Hudson Rock response: {str(e)}")
                    return []

        except httpx.TimeoutException:
            logger.error(f"Hudson Rock request timeout after {params.timeout}s")
            return []
        except Exception as e:
            logger.error(f"Error querying Hudson Rock: {str(e)}")
            return []

    def _summarize_results(self, stealers: List[Dict]) -> Dict[str, Any]:
        """Summarize stealer results"""
        total_credentials = 0
        malware_types = set()

        for stealer in stealers:
            total_credentials += stealer.get('compromised_count', 0)
            malware_name = stealer.get('malware_name')
            if malware_name:
                malware_types.add(malware_name)

        return {
            'total_stealers': len(stealers),
            'total_credentials': total_credentials,
            'malware_types': sorted(list(malware_types)),
            'is_compromised': len(stealers) > 0,
        }


# Standard interface for vanyshr-mono integration
async def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard entry point for vanyshr-mono scraper sequences.

    Args:
        params: {username, apiKey, timeout}

    Returns:
        Dictionary matching ScrapeOutput schema (JSON-serializable)
    """
    scraper = HudsonRockUsernameScraper(timeout=params.get("timeout", 30))
    output = await scraper.run(params)
    return asdict(output)

