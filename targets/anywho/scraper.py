# targets/anywho/scraper.py
"""
AnyWho Scraper

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

# Map state abbreviations to full names
STATE_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming", "DC": "district of columbia"
}


@dataclass
class ScraperParams:
    """Input parameters for AnyWho scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60  # context.dev Extract takes 10-30s per call


class AnyWhoScraper:
    """AnyWho scraper using context.dev Extract API for structured extraction"""

    BASE_URL = "https://www.anywho.com"

    # Schema for listing page extraction
    LISTING_SCHEMA = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Full name"},
                        "address": {"type": "string", "description": "Address"},
                        "age_range": {"type": "string", "description": "Age range"},
                        "location": {"type": "string", "description": "City, State"},
                        "profile_url": {"type": "string", "description": "Link to profile"}
                    }
                },
                "description": "Search results"
            }
        }
    }

    # Schema for detailed profile extraction
    PROFILE_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Full name"},
            "age": {"type": "string", "description": "Age or DOB"},
            "address": {"type": "string", "description": "Current address"},
            "phone": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Phone numbers"
            },
            "email": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Email addresses"
            },
            "family_members": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Family members / relatives"
            },
            "properties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Properties owned"
            }
        }
    }

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not self.api_key:
            raise ValueError("CONTEXT_DEV_API_KEY environment variable not set")
        self.client = ContextDev(api_key=self.api_key, timeout=timeout)

    def _build_search_url(self, params: ScraperParams) -> str:
        """
        Build AnyWho search URL.

        URL pattern: /people/{first}+{last}/{state-name}/{city}
        Example: /people/james+oehring/missouri/cameron
        """
        first = params.firstName.lower()
        last = params.lastName.lower()
        city = params.city.lower().replace(" ", "-")
        # Get full state name from abbreviation and replace spaces with hyphens
        state_full = STATE_NAMES.get(params.state.upper(), params.state.lower()).replace(" ", "-")

        return f"{self.BASE_URL}/people/{first}+{last}/{state_full}/{city}"

    def _extract_summary_results(self, extracted_data: Dict[str, Any]) -> List[SummaryResult]:
        """Convert listing page extract to SummaryResult objects"""
        results = []

        if not extracted_data or not extracted_data.get("results"):
            return results

        for result in extracted_data.get("results", []):
            if not result.get("name"):
                continue

            summary = SummaryResult(
                resultId="anywho_" + result.get("name", "").replace(" ", "_").lower(),
                fullName=result.get("name", ""),
                address=result.get("address", ""),
                ageRange=result.get("age_range", ""),
                location=result.get("location", ""),
                profileUrl=result.get("profile_url", "")
            )

            if summary.fullName:
                results.append(summary)

        return results

    def _parse_age(self, age_str: Optional[str]) -> Optional[int]:
        """Parse age string to int"""
        if not age_str:
            return None
        try:
            digits = re.findall(r'\d+', str(age_str))
            if digits:
                first_num = int(digits[0])
                if first_num > 1900 and first_num < 2100:
                    current_year = datetime.utcnow().year
                    return current_year - first_num
                elif first_num < 150:
                    return first_num
            return None
        except (ValueError, TypeError):
            return None

    def _extract_profile(self, extracted_data: Dict[str, Any]) -> Optional[Profile]:
        """Convert profile page extract to Profile object"""
        if not extracted_data or not extracted_data.get("name"):
            return None

        # Handle phone as array
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

        # Handle email as array
        emails = extracted_data.get("email", [])
        if isinstance(emails, str):
            emails = [emails] if emails else []
        email_addresses = [e for e in emails if e]

        profile = Profile(
            profileId="anywho_" + extracted_data.get("name", "").replace(" ", "_").lower(),
            fullName=extracted_data.get("name", ""),
            age=self._parse_age(extracted_data.get("age")),
            currentAddress={
                "formatted": extracted_data.get("address", "")
            } if extracted_data.get("address") else {},
            phoneNumbers=phone_numbers,
            emailAddresses=email_addresses,
            familyMembers=[
                {"name": member, "relationship": "family"}
                for member in (extracted_data.get("family_members") or [])
                if member
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
        Main entry point for scraping AnyWho.

        Args:
            params: Dictionary with keys: firstName, lastName, city, state, [timeout]

        Returns:
            ScrapeOutput with summary results and profile data
        """
        try:
            # Validate and normalize params
            scraper_params = ScraperParams(**params)

            logger.info(f"AnyWho Scrape started: {scraper_params.firstName} {scraper_params.lastName}, "
                       f"{scraper_params.city}, {scraper_params.state}")

            start_time = datetime.utcnow()

            # Step 1: Extract from listing page
            search_url = self._build_search_url(scraper_params)
            logger.debug(f"Fetching listing: {search_url}")

            listing_result = self.client.web.extract(
                url=search_url,
                schema=self.LISTING_SCHEMA,
                max_age_ms=86400000
            )

            # Convert listing data to summary results
            summary_results = self._extract_summary_results(listing_result.data) if listing_result.data else []

            # Step 2: Extract from profile page if available
            profile_data = None
            if summary_results and summary_results[0].profileUrl:
                profile_url = summary_results[0].profileUrl
                logger.debug(f"Fetching profile: {profile_url}")
                try:
                    profile_result = self.client.web.extract(
                        url=profile_url,
                        schema=self.PROFILE_SCHEMA,
                        max_age_ms=86400000
                    )
                    # Merge listing and profile data
                    merged_data = {**listing_result.data, **profile_result.data} if profile_result.data else listing_result.data
                    profile_data = self._extract_profile(profile_result.data) if profile_result.data else None
                except Exception as e:
                    logger.warning(f"Profile extraction failed, using listing data only: {e}")
                    if listing_result.data and listing_result.data.get("results"):
                        profile_data = self._extract_profile(listing_result.data["results"][0])
            else:
                # No profile URL, try to create profile from listing
                if listing_result.data and listing_result.data.get("results"):
                    profile_data = self._extract_profile(listing_result.data["results"][0])

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            status = "success" if (summary_results or profile_data) else "no_results"

            output = ScrapeOutput(
                source="anywho",
                search_params=asdict(scraper_params),
                summary_results=summary_results,
                profile=profile_data,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status=status
            )

            logger.info(f"AnyWho Scrape completed: {len(summary_results)} results, "
                       f"{execution_time_ms}ms, status={status}")

            return output

        except Exception as e:
            logger.error(f"AnyWho Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="anywho",
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

    Args:
        params: {firstName, lastName, city, state, timeout}

    Returns:
        Dictionary matching ScrapeOutput schema (JSON-serializable)
    """
    scraper = AnyWhoScraper(timeout=params.get("timeout", 60))
    output = scraper.run(params)
    return asdict(output)
