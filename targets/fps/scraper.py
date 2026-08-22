# targets/fps/scraper.py
"""
FPS (FastPeopleSearch) Scraper

Uses context.dev Extract API for structured data extraction.
Standard interface: run(params) -> ScrapeOutput
"""

import os
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

from context.dev import ContextDev

from .models import ScrapeOutput, SummaryResult, Profile

logger = logging.getLogger(__name__)


@dataclass
class ScraperParams:
    """Input parameters for FPS scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60  # context.dev Extract takes 10-30s per call


class FPSScraper:
    """FPS scraper using context.dev Extract API for structured extraction"""

    BASE_URL = "https://www.fastpeoplesearch.com"

    # Schema for listing page extraction
    LISTING_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full name of the person"
            },
            "age": {
                "type": "string",
                "description": "Age or age range"
            },
            "address": {
                "type": "string",
                "description": "Address preview"
            },
            "phone": {
                "type": "string",
                "description": "Phone number"
            },
            "profile_url": {
                "type": "string",
                "description": "Direct link to full profile"
            },
            "relatives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Known relatives"
            },
            "previous_addresses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Previous addresses lived at"
            }
        }
    }

    # Schema for detailed profile page extraction
    PROFILE_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full name"
            },
            "age": {
                "type": "string",
                "description": "Age"
            },
            "address": {
                "type": "string",
                "description": "Current address with full details"
            },
            "phone": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All associated phone numbers"
            },
            "email": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All associated email addresses"
            },
            "relatives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Family members"
            },
            "previous_addresses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All previous addresses"
            },
            "occupation": {
                "type": "string",
                "description": "Current or past occupation"
            },
            "education": {
                "type": "string",
                "description": "Educational background"
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
        Build FPS search URL.

        URL pattern: /name/{first}-{last}_{city}-{state}
        Example: /name/james-oehring_cameron-mo
        """
        first = params.firstName.lower()
        last = params.lastName.lower()
        city = params.city.lower().replace(" ", "-")
        state = params.state.lower()

        return f"{self.BASE_URL}/name/{first}-{last}_{city}-{state}"

    def _extract_summary_results(self, extracted_data: Dict[str, Any]) -> List[SummaryResult]:
        """Convert context.dev extract output to SummaryResult objects"""
        if not extracted_data or not extracted_data.get("name"):
            return []

        # Single result from FPS search
        summary = SummaryResult(
            resultId="fps_" + extracted_data.get("name", "").replace(" ", "_").lower(),
            fullName=extracted_data.get("name", ""),
            address=extracted_data.get("address", ""),
            age=self._parse_age(extracted_data.get("age")),
            phone=extracted_data.get("phone", ""),
            profileUrl=""  # FPS search results don't provide direct profile URL
        )

        return [summary] if summary.fullName else []

    def _parse_age(self, age_str: Optional[str]) -> Optional[int]:
        """Parse age string to int"""
        if not age_str:
            return None
        try:
            # Extract first number from age string (handles "61", "Age 61", "61 years old", etc)
            digits = re.findall(r'\d+', str(age_str))
            return int(digits[0]) if digits else None
        except (ValueError, TypeError):
            return None

    def _extract_profile(self, extracted_data: Dict[str, Any]) -> Optional[Profile]:
        """Convert context.dev extract output to Profile object"""
        if not extracted_data or not extracted_data.get("name"):
            return None

        # Handle phone as either string or array
        phones = extracted_data.get("phone", [])
        if isinstance(phones, str):
            phones = [phones] if phones else []
        phone_numbers = [
            {
                "number": phone,
                "type": "primary" if i == 0 else "secondary",
                "status": "current"
            }
            for i, phone in enumerate(phones)
            if phone
        ]

        # Handle email as either string or array
        emails = extracted_data.get("email", [])
        if isinstance(emails, str):
            emails = [emails] if emails else []
        email_addresses = [e for e in emails if e]

        profile = Profile(
            profileId="fps_" + extracted_data.get("name", "").replace(" ", "_").lower(),
            fullName=extracted_data.get("name", ""),
            age=self._parse_age(extracted_data.get("age")),
            currentAddress={
                "formatted": extracted_data.get("address", "")
            } if extracted_data.get("address") else {},
            previousAddresses=[
                {"formatted": addr}
                for addr in (extracted_data.get("previous_addresses") or [])
                if addr
            ],
            phoneNumbers=phone_numbers,
            emailAddresses=email_addresses,
            relatives=[
                {"name": rel, "relationship": "family"}
                for rel in (extracted_data.get("relatives") or [])
                if rel
            ],
            properties=[]
        )

        return profile if profile.fullName else None

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Main entry point for scraping FPS using context.dev Extract.

        Args:
            params: Dictionary with keys: firstName, lastName, city, state, [timeout]

        Returns:
            ScrapeOutput with summary results and profile data
        """
        try:
            # Validate and normalize params
            scraper_params = ScraperParams(**params)

            logger.info(f"FPS Scrape started: {scraper_params.firstName} {scraper_params.lastName}, "
                       f"{scraper_params.city}, {scraper_params.state}")

            start_time = datetime.utcnow()

            # Step 1: Extract from listing page
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching listing: {search_url}")

            listing_result = self.client.web.extract(
                url=search_url,
                schema=self.LISTING_SCHEMA,
                max_age_ms=86400000  # Cache for 24 hours (1 day)
            )

            # Convert listing data to summary results
            summary_results = self._extract_summary_results(listing_result.data) if listing_result.data else []

            # Step 2: Extract from profile page if available
            profile_data = None
            if listing_result.data and listing_result.data.get("profile_url"):
                profile_url = listing_result.data.get("profile_url")
                logger.debug(f"Fetching profile: {profile_url}")
                try:
                    profile_result = self.client.web.extract(
                        url=profile_url,
                        schema=self.PROFILE_SCHEMA,
                        max_age_ms=86400000
                    )
                    # Merge listing and profile data, profile takes precedence
                    merged_data = {**listing_result.data, **profile_result.data} if profile_result.data else listing_result.data
                    profile_data = self._extract_profile(merged_data)
                except Exception as e:
                    logger.warning(f"Profile extraction failed, using listing data only: {e}")
                    profile_data = self._extract_profile(listing_result.data)
            else:
                # No profile URL, use listing data for profile
                profile_data = self._extract_profile(listing_result.data) if listing_result.data else None

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            status = "success" if (summary_results or profile_data) else "no_results"

            output = ScrapeOutput(
                source="fps",
                search_params=asdict(scraper_params),
                summary_results=summary_results,
                profile=profile_data,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"FPS Scrape completed: {len(summary_results)} results, "
                       f"{execution_time_ms}ms, status={status}")

            return output

        except Exception as e:
            logger.error(f"FPS Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="fps",
                search_params=params,
                summary_results=[],
                profile=None,
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
    - QuickScan workflow (summary only)
    - Subscriber monitoring workflow (full profiles)

    Args:
        params: {firstName, lastName, city, state, timeout}

    Returns:
        Dictionary matching ScrapeOutput schema (JSON-serializable)
    """
    scraper = FPSScraper(timeout=params.get("timeout", 10))
    output = scraper.run(params)
    return asdict(output)

