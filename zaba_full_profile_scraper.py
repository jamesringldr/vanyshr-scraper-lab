#!/usr/bin/env python3
"""
Zaba Full Profile Scraper

Note: Zaba returns full profiles on search (not separate from summaries).
This scraper extracts enriched data from the residential service response.
"""

import logging
import os
from typing import Dict, Any, Optional, List

from targets.zaba.models import Profile

logger = logging.getLogger(__name__)


class ZabaFullProfileScraper:
    """
    Extracts full profile data from Zaba.

    Note: Zaba returns full profiles directly from search (not like other brokers).
    This class processes Zaba profile data to extract emails, phones, relatives, etc.
    """

    def __init__(self):
        """Initialize Zaba profile scraper"""
        pass

    def process_profile(
        self, zaba_profile_data: Dict[str, Any], profile_id: str = ""
    ) -> Optional[Profile]:
        """
        Process raw Zaba profile data and extract structured fields.

        Args:
            zaba_profile_data: Raw profile data from Zaba service
            profile_id: Optional profile ID for tracking

        Returns:
            Profile object with enriched data, or None if failed
        """
        try:
            if not zaba_profile_data or not isinstance(zaba_profile_data, dict):
                return None

            profile = Profile(profileId=profile_id)

            # Extract basic info
            profile.fullName = zaba_profile_data.get("fullName", "")
            profile.age = zaba_profile_data.get("age")

            # Extract current address
            current_addr = zaba_profile_data.get("currentAddress", {})
            if current_addr:
                formatted = self._format_address(current_addr)
                if formatted:
                    profile.currentAddress = {"formatted": formatted}

            # Extract emails (Zaba may have them in raw data)
            emails = zaba_profile_data.get("emailAddresses", [])
            if isinstance(emails, list):
                profile.emailAddresses = [e.lower() for e in emails if e]

            # Extract phone numbers
            phones = zaba_profile_data.get("phoneNumbers", [])
            if isinstance(phones, list):
                for phone in phones:
                    if isinstance(phone, dict):
                        profile.phoneNumbers.append(phone)
                    elif isinstance(phone, str):
                        profile.phoneNumbers.append({"number": phone})

            # Extract relatives
            relatives = zaba_profile_data.get("relatives", [])
            if isinstance(relatives, list):
                profile.relatives = [
                    {"name": r.get("name", ""), "relationship": "family"}
                    for r in relatives
                    if isinstance(r, dict) and r.get("name")
                ][:5]

            # Extract associates
            associates = zaba_profile_data.get("associates", [])
            if isinstance(associates, list):
                profile.associates = [
                    {"name": a.get("name", "")} for a in associates if isinstance(a, dict)
                ][:5]

            # Extract properties
            properties = zaba_profile_data.get("properties", [])
            if isinstance(properties, list):
                profile.properties = properties[:5]

            logger.debug(
                f"Processed Zaba profile: {profile.fullName}, "
                f"{len(profile.emailAddresses)} emails, "
                f"{len(profile.phoneNumbers)} phones"
            )

            return profile if profile.fullName else None

        except Exception as e:
            logger.error(f"Error processing Zaba profile: {e}", exc_info=True)
            return None

    @staticmethod
    def _format_address(addr_dict: Dict[str, Any]) -> str:
        """Format address dictionary to string"""
        if not addr_dict:
            return ""

        parts = []
        if addr_dict.get("streetAddress"):
            parts.append(addr_dict["streetAddress"])
        if addr_dict.get("addressLocality"):
            parts.append(addr_dict["addressLocality"])
        if addr_dict.get("addressRegion"):
            parts.append(addr_dict["addressRegion"])
        if addr_dict.get("postalCode"):
            parts.append(addr_dict["postalCode"])

        return ", ".join(parts) if parts else ""


def main():
    """Test Zaba profile processor"""
    # Mock Zaba profile data
    mock_profile = {
        "fullName": "James Oehring",
        "age": 61,
        "currentAddress": {
            "streetAddress": "413 Lovers Ln",
            "addressLocality": "Cameron",
            "addressRegion": "MO",
            "postalCode": "64429",
        },
        "emailAddresses": ["james@example.com"],
        "phoneNumbers": [{"number": "(816) 225-8592"}],
        "relatives": [{"name": "Rickilinda Oehring"}],
    }

    scraper = ZabaFullProfileScraper()
    profile = scraper.process_profile(mock_profile, "zaba_test_1")

    if profile:
        print(f"✅ Processed Zaba profile: {profile.fullName}")
        print(f"   Age: {profile.age}")
        print(f"   Address: {profile.currentAddress}")
        print(f"   Emails: {profile.emailAddresses}")
        print(f"   Relatives: {len(profile.relatives)}")
    else:
        print("❌ Failed to process profile")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
