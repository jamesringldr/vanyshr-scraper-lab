"""
Zaba Residential Scraper — Using serv01:8788 service.

This scraper uses the residential IP service running on serv01 (port 8788)
instead of context.dev HTML method (which gets IP-blocked).

Service endpoint format:
  - Local (development): http://localhost:8788/v1/zaba/search
  - Prod (serv01): Uses ZABA_PROD_URL environment variable
  - Fallback: Uses ZABA_LOCAL_URL if ZABA_PROD_URL not set
"""

import logging
import os
from typing import Dict, Any, Optional

import httpx

from targets.zaba.models import ScrapeOutput, SummaryResult

logger = logging.getLogger(__name__)


class ZabaResidentialScraper:
    """
    Scrapes Zaba using the residential IP service on serv01.
    Calls HTTP endpoint instead of context.dev.
    """

    def __init__(self, timeout: int = 60, use_prod: bool = True):
        """
        Initialize Zaba residential scraper.

        Args:
            timeout: Request timeout in seconds
            use_prod: Use production serv01 (True) or localhost (False)
        """
        self.timeout = timeout
        self.use_prod = use_prod

        # Get URLs from environment
        self.prod_url = os.getenv("ZABA_PROD_URL", "").rstrip("/")
        self.local_url = os.getenv("ZABA_LOCAL_URL", "http://localhost:8788").rstrip("/")
        self.service_token = os.getenv("ZABA_SERVICE_TOKEN", "")

        # Select endpoint
        if use_prod and self.prod_url:
            self.base_url = self.prod_url
            self.use_auth = bool(self.service_token)
        else:
            self.base_url = self.local_url
            self.use_auth = False

        logger.info(
            f"ZabaResidentialScraper initialized: {self.base_url} "
            f"(auth={self.use_auth})"
        )

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Run the scraper (synchronous).

        Args:
            params: Dict with first_name, last_name, city, state, timeout

        Returns:
            ScrapeOutput with summaries or error
        """
        import time
        start_time = time.time()

        # Extract parameters
        first_name = params.get("firstName", "")
        last_name = params.get("lastName", "")
        city = params.get("city")
        state = params.get("state")
        timeout = params.get("timeout", self.timeout)

        if not first_name or not last_name:
            return ScrapeOutput(
                source="zaba",
                search_params=params,
                status="failed",
                error="first_name and last_name required",
            )

        # Build request
        endpoint = f"{self.base_url}/v1/zaba/search"
        body = {
            "first_name": first_name,
            "last_name": last_name,
            "city": city or None,
            "state": state or None,
        }
        headers = {"Content-Type": "application/json"}
        if self.use_auth:
            headers["Authorization"] = f"Bearer {self.service_token}"

        logger.info(
            f"Zaba residential scrape: {first_name} {last_name}, "
            f"{city}, {state}"
        )
        logger.debug(f"POST {endpoint} body={body}")

        try:
            # Use blocking HTTP client
            response = httpx.post(
                endpoint,
                json=body,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            timing_ms = int((time.time() - start_time) * 1000)

            # Parse response
            status = data.get("status", "failed")
            if status != "success":
                error = data.get("error", "Unknown error from serv01")
                logger.warning(f"Zaba residential returned {status}: {error}")
                return ScrapeOutput(
                    source="zaba",
                    search_params=params,
                    status=status,
                    error=error,
                    execution_time_ms=timing_ms,
                )

            # Extract summaries from response
            summary_results = self._parse_summaries(data)

            logger.info(
                f"Zaba residential scraped: {len(summary_results)} profiles, "
                f"{timing_ms}ms"
            )

            return ScrapeOutput(
                source="zaba",
                search_params=params,
                summary_results=summary_results,
                status="success",
                execution_time_ms=timing_ms,
            )

        except httpx.TimeoutException:
            timing_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Zaba residential timeout after {timeout}s")
            return ScrapeOutput(
                source="zaba",
                search_params=params,
                status="failed",
                error=f"timeout after {timeout}s",
                execution_time_ms=timing_ms,
            )

        except Exception as e:
            timing_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Zaba residential error: {e}", exc_info=True)
            return ScrapeOutput(
                source="zaba",
                search_params=params,
                status="failed",
                error=str(e),
                execution_time_ms=timing_ms,
            )

    def _parse_summaries(self, data: Dict[str, Any]) -> list:
        """
        Parse summaries from serv01 response.

        Expected response format (from workers/zaba/service.py):
        {
            "status": "success",
            "summaries": [
                {
                    "fullName": "James Oehring",
                    "age": "37",
                    "address": "413 Lovers Ln, Cameron, MO 64429",
                    "location": "Cameron, MO"
                },
                ...
            ]
        }

        Args:
            data: Response JSON from serv01

        Returns:
            List of SummaryResult objects
        """
        summaries = []

        raw_summaries = data.get("summaries", [])
        logger.debug(f"Parsing {len(raw_summaries)} raw summaries from serv01")

        for i, item in enumerate(raw_summaries):
            try:
                # Parse age
                age_str = item.get("age", "")
                age = None
                if age_str:
                    try:
                        age = int(age_str)
                    except (ValueError, TypeError):
                        age = None

                summary = SummaryResult(
                    resultId=f"zaba_{i}",  # Generate unique ID
                    fullName=item.get("fullName", ""),
                    address=item.get("address", ""),
                    age=age,
                )
                summaries.append(summary)

            except Exception as e:
                logger.warning(f"Error parsing Zaba summary: {e}")

        return summaries


async def main():
    """Test Zaba residential scraper with real data"""
    logging.basicConfig(level=logging.INFO)

    # Test with James Oehring (this should work if serv01 is running)
    scraper = ZabaResidentialScraper(use_prod=False)  # Use localhost for testing

    result = scraper.run({
        "firstName": "James",
        "lastName": "Oehring",
        "city": "Cameron",
        "state": "MO",
        "timeout": 30,
    })

    print("\n" + "=" * 80)
    print("ZABA RESIDENTIAL SCRAPER TEST")
    print("=" * 80)
    print(f"Status: {result.status}")
    print(f"Error: {result.error}")
    print(f"Timing: {result.execution_time_ms}ms")
    print(f"Summaries: {len(result.summary_results)}")

    for i, summary in enumerate(result.summary_results, 1):
        print(f"\n  Profile {i}:")
        print(f"    Name: {summary.fullName}")
        print(f"    Age: {summary.age}")
        print(f"    Address: {summary.address}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
