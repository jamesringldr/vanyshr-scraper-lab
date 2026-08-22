# targets/zaba/scraper.py
"""
Zaba Scraper

Uses context.dev Extract API for structured data extraction.
Standard interface: run(params) -> ScrapeOutput

Note: Zaba returns all results on a single page (no separate profile pages).
All results are full profiles displayed as blocks on the same page.
"""

import os
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

from context.dev import ContextDev

from .models import ScrapeOutput, Profile

logger = logging.getLogger(__name__)


@dataclass
class ScraperParams:
    """Input parameters for Zaba scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60  # context.dev Extract takes 10-30s per call


class ZabaScraper:
    """Zaba scraper using context.dev Extract API for structured extraction"""

    BASE_URL = "https://search.zaba.com"
    SEARCH_PATH = "/s"

    # Schema for extracting multiple profiles from single search page
    SEARCH_SCHEMA = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Full name of the person"
                        },
                        "age": {
                            "type": "string",
                            "description": "Age"
                        },
                        "address": {
                            "type": "string",
                            "description": "Current address (street, city, state, zip)"
                        },
                        "phone": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "All phone numbers"
                        },
                        "email": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "All email addresses"
                        },
                        "relatives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Family members"
                        },
                        "associates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Known associates"
                        },
                        "properties": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Real estate properties"
                        }
                    }
                },
                "description": "All search results as full profiles"
            }
        }
    }

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not self.api_key:
            raise ValueError("CONTEXT_DEV_API_KEY environment variable not set")
        # Pass timeout to ContextDev client (in seconds)
        self.client = ContextDev(api_key=self.api_key, timeout=timeout)

    def _build_search_url(self, params: ScraperParams) -> str:
        """
        Build Zaba search URL.

        URL pattern: /s?q=[FirstName]+[LastName]&where=[City],+[State]
        Example: /s?q=james+oehring&where=cameron,+mo
        """
        first = params.firstName
        last = params.lastName
        city = params.city
        state = params.state.lower()

        query = f"{first}+{last}".replace(" ", "+")
        where = f"{city},+{state}".replace(" ", "+")

        return f"{self.BASE_URL}{self.SEARCH_PATH}?q={query}&where={where}"

    def _parse_age(self, age_str: Optional[str]) -> Optional[int]:
        """Parse age string to int"""
        if not age_str:
            return None
        try:
            # Extract first number from age string
            digits = re.findall(r'\d+', str(age_str))
            if digits:
                first_num = int(digits[0])
                # If it looks like a year, calculate age
                if first_num > 1900 and first_num < 2100:
                    current_year = datetime.utcnow().year
                    return current_year - first_num
                # Otherwise return as age
                elif first_num < 150:
                    return first_num
            return None
        except (ValueError, TypeError):
            return None

    def _extract_profiles(self, extracted_data: Dict[str, Any]) -> List[Profile]:
        """Convert context.dev extract output to Profile objects"""
        profiles = []

        if not extracted_data or not extracted_data.get("results"):
            return profiles

        for i, result in enumerate(extracted_data.get("results", [])):
            if not result.get("name"):
                continue

            # Handle phone as array
            phones = result.get("phone", [])
            if isinstance(phones, str):
                phones = [phones] if phones else []
            phone_numbers = [
                {
                    "number": phone,
                    "type": "primary" if j == 0 else "secondary",
                    "status": "current"
                }
                for j, phone in enumerate(phones)
                if phone
            ]

            # Handle email as array
            emails = result.get("email", [])
            if isinstance(emails, str):
                emails = [emails] if emails else []
            email_addresses = [e for e in emails if e]

            profile = Profile(
                profileId="zaba_" + result.get("name", "").replace(" ", "_").lower() + f"_{i}",
                fullName=result.get("name", ""),
                age=self._parse_age(result.get("age")),
                currentAddress={
                    "formatted": result.get("address", "")
                } if result.get("address") else {},
                phoneNumbers=phone_numbers,
                emailAddresses=email_addresses,
                # Associates folded in here too (see targets/zaba/models.py) --
                # already distinguishable via "relationship".
                relatives=[
                    {"name": rel, "relationship": "family"}
                    for rel in (result.get("relatives") or [])
                    if rel
                ] + [
                    {"name": assoc, "relationship": "associate"}
                    for assoc in (result.get("associates") or [])
                    if assoc
                ],
                properties=[
                    {"address": prop, "propertyType": "residential"}
                    for prop in (result.get("properties") or [])
                    if prop
                ]
            )

            if profile.fullName:
                profiles.append(profile)

        return profiles

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
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

            # Build search URL and extract all profiles
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching: {search_url}")

            # Extract all profiles from single search page with caching
            result = self.client.web.extract(
                url=search_url,
                schema=self.SEARCH_SCHEMA,
                max_age_ms=86400000  # Cache for 24 hours (1 day)
            )

            # Convert extracted data to profile objects
            profiles = self._extract_profiles(result.data) if result.data else []

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            status = "success" if profiles else "no_results"

            output = ScrapeOutput(
                source="zaba",
                search_params=asdict(scraper_params),
                summary_results=[],  # No summary page for Zaba
                profiles=profiles,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"Zaba Scrape completed: {len(profiles)} profiles, "
                       f"{execution_time_ms}ms, status={status}")

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


# Standard interface for vanyshr-mono integration
def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard entry point for vanyshr scraper sequences.

    This function is imported and called by:
    - QuickScan workflow (returns all profiles found)
    - Subscriber monitoring workflow (returns all profiles found)

    Args:
        params: {firstName, lastName, city, state, timeout}

    Returns:
        Dictionary matching ScrapeOutput schema (JSON-serializable)
    """
    scraper = ZabaScraper(timeout=params.get("timeout", 60))
    output = scraper.run(params)
    return asdict(output)
