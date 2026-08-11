#!/usr/bin/env python3
"""
Leakcheck Enricher

Calls Leakcheck API to find data breaches involving an email address.
https://leakcheck.io

Leakcheck aggregates data from 500+ publicly available breaches and data sources.
"""

import logging
import os
from typing import Dict, List, Set, Optional
import time

import httpx

logger = logging.getLogger(__name__)


class LeakcheckEnricher:
    """Enriches emails with breach data from Leakcheck"""

    # Leakcheck API endpoint
    LEAKCHECK_API_URL = "https://leakcheck.io/api/v2/query"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize Leakcheck enricher.

        Args:
            api_key: Leakcheck API key (optional, can also get from LEAKCHECK_API_KEY env var)
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key or os.getenv("LEAKCHECK_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            logger.warning(
                "No Leakcheck API key provided. "
                "Leakcheck API requires authentication. "
                "Set LEAKCHECK_API_KEY environment variable."
            )

    def enrich_email(self, email: str) -> Optional[Dict]:
        """
        Find data breaches involving an email.

        Args:
            email: Email address to check

        Returns:
            Dict with:
            {
                'email': 'user@example.com',
                'breaches': [
                    {'name': 'LinkedIn 2021', 'date': '2021-06-01', ...},
                    {'name': 'Facebook 2019', 'date': '2019-07-15', ...},
                ],
                'total_breaches': 2,
                'status': 'success' | 'failed'
            }
            Or None if request failed
        """
        if not email or not self._is_valid_email(email):
            logger.warning(f"Invalid email: {email}")
            return None

        if not self.api_key:
            logger.warning(f"No API key for Leakcheck, skipping: {email}")
            return {
                "email": email,
                "breaches": [],
                "status": "no_auth",
                "message": "Leakcheck API key not configured",
            }

        logger.info(f"Checking Leakcheck for breaches: {email}")

        try:
            # Make request to Leakcheck API
            response = httpx.get(
                self.LEAKCHECK_API_URL,
                params={
                    "email": email,
                    "type": "email",
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Vanyshr Scanner)",
                    "X-API-Key": self.api_key,
                },
                timeout=self.timeout,
            )

            # Leakcheck returns 404 if not found (which is good)
            if response.status_code == 404:
                logger.info(f"No breaches found for {email}")
                return {
                    "email": email,
                    "breaches": [],
                    "status": "success",
                    "found": False,
                }

            response.raise_for_status()
            data = response.json()

            # Parse response
            breaches = self._parse_leakcheck_response(data)

            result = {
                "email": email,
                "breaches": breaches,
                "total_breaches": len(breaches),
                "status": "success",
                "found": len(breaches) > 0,
            }

            if breaches:
                logger.warning(
                    f"Found {len(breaches)} breaches for {email}: "
                    f"{', '.join(b.get('name', 'Unknown')[:20] for b in breaches[:3])}"
                )

            return result

        except httpx.TimeoutException:
            logger.warning(f"Leakcheck timeout for {email}")
            return {
                "email": email,
                "breaches": [],
                "status": "timeout",
            }
        except Exception as e:
            logger.error(f"Error checking Leakcheck for {email}: {e}")
            return {
                "email": email,
                "breaches": [],
                "status": "failed",
                "error": str(e),
            }

    def enrich_emails_batch(
        self, emails: Set[str], delay_between_requests: float = 1.0
    ) -> Dict[str, Dict]:
        """
        Check multiple emails for breaches.

        Args:
            emails: Set of email addresses to check
            delay_between_requests: Delay between API calls (seconds) to avoid rate limiting

        Returns:
            Dict of {email: breach_result}
        """
        results = {}

        for i, email in enumerate(sorted(emails)):
            try:
                result = self.enrich_email(email)
                if result:
                    results[email] = result

                # Respect rate limits (Leakcheck may have strict limits)
                if i < len(emails) - 1 and delay_between_requests > 0:
                    time.sleep(delay_between_requests)

            except Exception as e:
                logger.error(f"Error checking {email}: {e}")
                results[email] = {
                    "email": email,
                    "breaches": [],
                    "status": "failed",
                    "error": str(e),
                }

        breach_count = sum(
            r.get("total_breaches", 0)
            for r in results.values()
            if r.get("status") == "success"
        )
        affected_count = sum(
            1
            for r in results.values()
            if r.get("status") == "success" and r.get("found")
        )

        logger.info(
            f"Checked {len(results)} emails. "
            f"Found {affected_count} emails in {breach_count} total breaches"
        )

        return results

    @staticmethod
    def _parse_leakcheck_response(data: Dict) -> List[Dict]:
        """
        Parse Leakcheck API response and extract breach information.

        Leakcheck returns format like:
        {
            "result": [
                {
                    "name": "LinkedIn",
                    "date": 1623265200,
                    "sources": ["..."],
                    ...
                },
                ...
            ]
        }

        Args:
            data: Response JSON from Leakcheck API

        Returns:
            List of breach dicts
        """
        breaches = []

        try:
            results = data.get("result", [])

            if isinstance(results, list):
                for breach in results:
                    if isinstance(breach, dict):
                        breach_info = {
                            "name": breach.get("name", "Unknown"),
                            "date": breach.get("date"),
                            "source": breach.get("source", "leakcheck"),
                        }
                        breaches.append(breach_info)

            # Sort by date (most recent first)
            breaches.sort(key=lambda x: x.get("date") or 0, reverse=True)

            return breaches

        except Exception as e:
            logger.warning(f"Error parsing Leakcheck response: {e}")
            return []

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validate email format"""
        if not email or not isinstance(email, str):
            return False

        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))


def main():
    """Test Leakcheck enricher"""
    enricher = LeakcheckEnricher()

    print("Leakcheck enricher initialized")
    print(f"API Key configured: {bool(enricher.api_key)}")
    print()

    if not enricher.api_key:
        print("⚠️  No Leakcheck API key - cannot check for breaches")
        print("Set LEAKCHECK_API_KEY environment variable to enable")
        print()
        print("Get free API key from: https://leakcheck.io")
        return

    # Test with a known email
    test_email = "test@example.com"
    result = enricher.enrich_email(test_email)

    if result:
        print(f"Email: {result['email']}")
        print(f"Status: {result['status']}")
        print(f"Breaches found: {result.get('total_breaches', 0)}")
        if result.get("breaches"):
            for breach in result["breaches"][:3]:
                print(f"  - {breach.get('name')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
