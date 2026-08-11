#!/usr/bin/env python3
"""
Holehe Enricher

Calls Holehe API to find which online services a person's email is registered with.
https://holehe.io

Holehe checks 100+ services: GitHub, LinkedIn, Twitter, Instagram, Facebook, etc.
"""

import logging
from typing import Dict, List, Set, Optional
import time

import httpx

logger = logging.getLogger(__name__)


class HoleheEnricher:
    """Enriches emails with service registration data from Holehe"""

    # Holehe public API endpoint
    HOLEHE_API_URL = "https://api.holehe.io/v1/email"

    # Services to display (most relevant for identity verification)
    PRIORITY_SERVICES = [
        "github",
        "linkedin",
        "twitter",
        "instagram",
        "facebook",
        "instagram",
        "pinterest",
        "tiktok",
        "snapchat",
        "reddit",
        "medium",
        "discord",
        "slack",
        "telegram",
        "whatsapp",
    ]

    def __init__(self, timeout: int = 30):
        """
        Initialize Holehe enricher.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout

    def enrich_email(self, email: str) -> Optional[Dict[str, any]]:
        """
        Find which services an email is registered with.

        Args:
            email: Email address to check

        Returns:
            Dict with:
            {
                'email': 'user@example.com',
                'services_found': ['github', 'linkedin', 'twitter'],
                'total_services': 3,
                'timestamp': '2026-08-11T...',
                'status': 'success' | 'failed'
            }
            Or None if request failed
        """
        if not email or not self._is_valid_email(email):
            logger.warning(f"Invalid email: {email}")
            return None

        logger.info(f"Enriching email with Holehe: {email}")

        try:
            # Make request to Holehe API
            response = httpx.get(
                self.HOLEHE_API_URL,
                params={"email": email},
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0 (Vanyshr Scanner)"},
            )

            response.raise_for_status()
            data = response.json()

            # Parse response
            services = self._parse_holehe_response(data)

            result = {
                "email": email,
                "services_found": services,
                "total_services": len(services),
                "status": "success",
            }

            logger.info(
                f"Found {len(services)} services for {email}: "
                f"{', '.join(services[:5])}{'...' if len(services) > 5 else ''}"
            )

            return result

        except httpx.TimeoutException:
            logger.warning(f"Holehe timeout for {email}")
            return {
                "email": email,
                "services_found": [],
                "status": "timeout",
            }
        except Exception as e:
            logger.error(f"Error enriching {email} with Holehe: {e}")
            return {
                "email": email,
                "services_found": [],
                "status": "failed",
                "error": str(e),
            }

    def enrich_emails_batch(
        self, emails: Set[str], delay_between_requests: float = 0.1
    ) -> Dict[str, Dict]:
        """
        Enrich multiple emails with Holehe data.

        Args:
            emails: Set of email addresses to check
            delay_between_requests: Delay between API calls (seconds) to avoid rate limiting

        Returns:
            Dict of {email: enrichment_result}
        """
        results = {}

        for i, email in enumerate(sorted(emails)):
            try:
                result = self.enrich_email(email)
                if result:
                    results[email] = result

                # Respect rate limits
                if i < len(emails) - 1 and delay_between_requests > 0:
                    time.sleep(delay_between_requests)

            except Exception as e:
                logger.error(f"Error enriching {email}: {e}")
                results[email] = {
                    "email": email,
                    "services_found": [],
                    "status": "failed",
                    "error": str(e),
                }

        logger.info(
            f"Enriched {len(results)} emails. "
            f"Found services in {sum(1 for r in results.values() if r.get('services_found'))} emails"
        )

        return results

    @staticmethod
    def _parse_holehe_response(data: Dict) -> List[str]:
        """
        Parse Holehe API response and extract service names.

        Holehe returns format like:
        {
            "email": "user@example.com",
            "results": {
                "Github": {"exists": True},
                "LinkedIn": {"exists": True},
                "Twitter": {"exists": False},
                ...
            }
        }

        Args:
            data: Response JSON from Holehe API

        Returns:
            List of service names where email is found
        """
        services = []

        try:
            results = data.get("results", {})

            if isinstance(results, dict):
                for service_name, service_data in results.items():
                    if isinstance(service_data, dict) and service_data.get("exists"):
                        services.append(service_name.lower())

            # Sort by priority
            priority_services = [
                s for s in services if s in HoleheEnricher.PRIORITY_SERVICES
            ]
            other_services = [
                s for s in services if s not in HoleheEnricher.PRIORITY_SERVICES
            ]

            return sorted(priority_services) + sorted(other_services)

        except Exception as e:
            logger.warning(f"Error parsing Holehe response: {e}")
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
    """Test Holehe enricher"""
    enricher = HoleheEnricher()

    # Test with a known email
    test_emails = {"james@example.com", "test@github.com"}

    print("Testing Holehe enricher...")
    print()

    for email in test_emails:
        result = enricher.enrich_email(email)
        if result:
            print(f"Email: {result['email']}")
            print(f"Status: {result['status']}")
            print(f"Services found: {result.get('services_found', [])}")
            print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
