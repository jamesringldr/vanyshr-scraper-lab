# targets/npd/scraper.py
"""
NPD (National Public Data) Scraper

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
    """Input parameters for NPD scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60  # context.dev Extract takes 10-30s per call


class NPDScraper:
    """NPD scraper using context.dev Extract API for structured extraction"""

    BASE_URL = "https://nationalpublicdata.com"

    # Schema for context.dev extraction
    EXTRACT_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full name of the person"
            },
            "age": {
                "type": "string",
                "description": "Age or date of birth"
            },
            "address": {
                "type": "string",
                "description": "Current address (street, city, state, zip)"
            },
            "phone": {
                "type": "string",
                "description": "Phone number"
            },
            "email": {
                "type": "string",
                "description": "Email address"
            },
            "relatives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Known relatives or family members"
            },
            "previous_addresses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Previous addresses lived at"
            },
            "properties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Real estate properties owned or associated"
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
        Build NPD search URL.

        URL pattern: /people/{letter}/{first}-{last}/{state-abbr}/{city}/
        Example: /people/o/james-oehring/mo/cameron/
        """
        first = params.firstName.lower()
        last = params.lastName.lower()
        letter = last[0] if last else ""
        city = params.city.lower().replace(" ", "-")
        state = params.state.lower()

        return f"{self.BASE_URL}/people/{letter}/{first}-{last}/{state}/{city}/"

    def _extract_summary_results(self, extracted_data: Dict[str, Any]) -> List[SummaryResult]:
        """Convert context.dev extract output to SummaryResult objects"""
        if not extracted_data or not extracted_data.get("name"):
            return []

        # Single result from NPD search
        summary = SummaryResult(
            resultId="npd_" + extracted_data.get("name", "").replace(" ", "_").lower(),
            fullName=extracted_data.get("name", ""),
            addressPreview=extracted_data.get("address", ""),
            phonePreview=extracted_data.get("phone", ""),
            matchScore=100 if extracted_data.get("name") else 0,  # 100% if name found
            profileUrl=""  # NPD search results don't provide direct profile URL
        )

        return [summary] if summary.fullName else []

    def _parse_age(self, age_str: Optional[str]) -> Optional[int]:
        """Parse age string to int"""
        if not age_str:
            return None
        try:
            # Extract first number from age string (handles "61", "DOB: 1963", etc)
            digits = re.findall(r'\d+', str(age_str))
            if digits:
                # If it looks like a year (19xx or 20xx), calculate age
                first_num = int(digits[0])
                if first_num > 1900 and first_num < 2100:
                    current_year = datetime.utcnow().year
                    return current_year - first_num
                # Otherwise return the number as age
                elif first_num < 150:
                    return first_num
            return None
        except (ValueError, TypeError):
            return None

    def _extract_profile(self, extracted_data: Dict[str, Any]) -> Optional[Profile]:
        """Convert context.dev extract output to Profile object"""
        if not extracted_data or not extracted_data.get("name"):
            return None

        profile = Profile(
            profileId="npd_" + extracted_data.get("name", "").replace(" ", "_").lower(),
            fullName=extracted_data.get("name", ""),
            dateOfBirth=None,  # Could parse from age string if needed
            age=self._parse_age(extracted_data.get("age")),
            currentAddress={
                "formatted": extracted_data.get("address", "")
            } if extracted_data.get("address") else {},
            previousAddresses=[
                {"formatted": addr}
                for addr in (extracted_data.get("previous_addresses") or [])
                if addr
            ],
            phoneNumbers=[
                {
                    "number": extracted_data.get("phone", ""),
                    "type": "primary",
                    "status": "current"
                }
            ] if extracted_data.get("phone") else [],
            emailAddresses=[extracted_data.get("email")] if extracted_data.get("email") else [],
            relatives=[
                {"name": rel, "relationship": "family"}
                for rel in (extracted_data.get("relatives") or [])
                if rel
            ],
            properties=[
                {"address": prop, "propertyType": "residential"}
                for prop in (extracted_data.get("properties") or [])
                if prop
            ]
        )

        return profile if profile.fullName else None

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Main entry point for scraping NPD using context.dev Extract.

        Args:
            params: Dictionary with keys: firstName, lastName, city, state, [timeout]

        Returns:
            ScrapeOutput with summary results and profile data
        """
        try:
            # Validate and normalize params
            scraper_params = ScraperParams(**params)

            logger.info(f"NPD Scrape started: {scraper_params.firstName} {scraper_params.lastName}, "
                       f"{scraper_params.city}, {scraper_params.state}")

            start_time = datetime.utcnow()

            # Build search URL and extract data using context.dev
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching: {search_url}")

            # Extract with optimization:
            # - maxAgeMs: cache for 24h to avoid redundant API calls for same query
            result = self.client.web.extract(
                url=search_url,
                schema=self.EXTRACT_SCHEMA,
                max_age_ms=86400000  # Cache for 24 hours (1 day)
            )

            # Convert extracted data to output models
            summary_results = self._extract_summary_results(result.data) if result.data else []
            profile_data = self._extract_profile(result.data) if result.data else None

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            status = "success" if (summary_results or profile_data) else "no_results"

            output = ScrapeOutput(
                source="npd",
                search_params=asdict(scraper_params),
                summary_results=summary_results,
                profile=profile_data,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"NPD Scrape completed: {len(summary_results)} results, "
                       f"{execution_time_ms}ms, status={status}")

            return output

        except Exception as e:
            logger.error(f"NPD Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="npd",
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
    scraper = NPDScraper(timeout=params.get("timeout", 60))
    output = scraper.run(params)
    return asdict(output)
