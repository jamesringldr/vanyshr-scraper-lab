#!/usr/bin/env python3
"""
Profile Consolidator

Merges profile data from multiple brokers into a single unified profile.
Handles deduplication of addresses, phones, and consolidation of enrichment data.
"""

import logging
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from targets.fps.models import Profile

logger = logging.getLogger(__name__)


@dataclass
class ConsolidatedProfile:
    """Unified profile combining data from all brokers"""

    # Core identity
    person_id: str
    full_name: str = ""
    age: Optional[int] = None

    # Addresses (deduplicated)
    primary_address: Dict[str, str] = field(default_factory=dict)
    previous_addresses: List[Dict[str, str]] = field(default_factory=list)

    # Contact info (deduplicated)
    phone_numbers: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)

    # Relations
    relatives: List[Dict[str, str]] = field(default_factory=list)
    associates: List[Dict[str, str]] = field(default_factory=list)

    # Properties
    properties: List[Dict[str, Any]] = field(default_factory=list)

    # Enrichment data
    services_found: List[str] = field(default_factory=list)
    breaches: List[Dict[str, Any]] = field(default_factory=list)

    # Raw data (for audit trail and transparency)
    raw_profiles: Dict[str, Profile] = field(default_factory=dict)

    # Metadata
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "person_id": self.person_id,
            "full_name": self.full_name,
            "age": self.age,
            "primary_address": self.primary_address,
            "previous_addresses": self.previous_addresses,
            "phone_numbers": self.phone_numbers,
            "emails": self.emails,
            "relatives": self.relatives,
            "associates": self.associates,
            "properties": self.properties,
            "services_found": self.services_found,
            "breaches": self.breaches,
            "confidence": self.confidence,
            "sources": self.sources,
            "metadata": self.metadata,
        }


class ProfileConsolidator:
    """Consolidates profiles from multiple brokers into a unified profile"""

    # Address similarity threshold (0-1)
    ADDRESS_SIMILARITY_THRESHOLD = 0.7

    def __init__(self):
        """Initialize consolidator"""
        pass

    def consolidate(
        self,
        profiles: Dict[str, Profile],
        person_id: str,
        confidence: float = 0.0,
        enrichment_data: Optional[Dict[str, Any]] = None,
    ) -> ConsolidatedProfile:
        """
        Consolidate profiles from multiple brokers.

        Args:
            profiles: Dict of {broker_name: Profile}
            person_id: Unique person identifier
            confidence: Dedup confidence from Phase 1 (0-100)
            enrichment_data: Dict with 'services_found' and 'breaches' keys

        Returns:
            ConsolidatedProfile with merged data
        """
        logger.info(f"Consolidating {len(profiles)} profiles into unified profile")

        consolidated = ConsolidatedProfile(person_id=person_id, confidence=confidence)

        # Extract basic info from first profile with name
        for broker, profile in profiles.items():
            if profile and profile.fullName:
                consolidated.full_name = profile.fullName
                consolidated.age = profile.age
                break

        # Consolidate each data type
        consolidated.phone_numbers = self._consolidate_phones(profiles)
        consolidated.emails = self._consolidate_emails(profiles)
        consolidated.primary_address, consolidated.previous_addresses = (
            self._consolidate_addresses(profiles)
        )
        consolidated.relatives = self._consolidate_relatives(profiles)
        consolidated.associates = self._consolidate_associates(profiles)
        consolidated.properties = self._consolidate_properties(profiles)

        # Add enrichment data
        if enrichment_data:
            consolidated.services_found = enrichment_data.get("services_found", [])
            consolidated.breaches = enrichment_data.get("breaches", [])

        # Store raw profiles and sources
        consolidated.raw_profiles = profiles
        consolidated.sources = [b for b, p in profiles.items() if p and p.fullName]

        logger.info(
            f"Consolidated profile: {consolidated.full_name}, "
            f"{len(consolidated.phone_numbers)} phones, "
            f"{len(consolidated.emails)} emails, "
            f"{len(consolidated.services_found)} services"
        )

        return consolidated

    def _consolidate_phones(self, profiles: Dict[str, Profile]) -> List[str]:
        """
        Extract and deduplicate phone numbers from all profiles.

        Args:
            profiles: Dict of broker profiles

        Returns:
            List of unique phone numbers
        """
        phones = set()

        for broker, profile in profiles.items():
            if not profile or not hasattr(profile, "phoneNumbers"):
                continue

            for phone_obj in profile.phoneNumbers:
                if isinstance(phone_obj, dict):
                    phone = phone_obj.get("number", "")
                elif isinstance(phone_obj, str):
                    phone = phone_obj
                else:
                    continue

                # Normalize phone number (remove all non-digits, then check length)
                import re

                digits = re.sub(r"\D", "", str(phone))
                if len(digits) == 10:  # Valid US phone
                    normalized = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                    phones.add(normalized)

        logger.debug(f"Consolidated {len(phones)} unique phone numbers")
        return sorted(list(phones))

    def _consolidate_emails(self, profiles: Dict[str, Profile]) -> List[str]:
        """
        Extract and deduplicate email addresses from all profiles.

        Args:
            profiles: Dict of broker profiles

        Returns:
            List of unique email addresses
        """
        emails = set()

        for broker, profile in profiles.items():
            if not profile or not hasattr(profile, "emailAddresses"):
                continue

            for email in profile.emailAddresses:
                if email and isinstance(email, str):
                    email = email.lower().strip()
                    # Basic validation
                    if "@" in email and "." in email:
                        emails.add(email)

        logger.debug(f"Consolidated {len(emails)} unique email addresses")
        return sorted(list(emails))

    def _consolidate_addresses(
        self, profiles: Dict[str, Profile]
    ) -> tuple[Dict[str, str], List[Dict[str, str]]]:
        """
        Extract and deduplicate addresses using string similarity.

        Args:
            profiles: Dict of broker profiles

        Returns:
            (primary_address, previous_addresses)
        """
        all_addresses = []

        for broker, profile in profiles.items():
            if not profile:
                continue

            # Current address
            if hasattr(profile, "currentAddress") and profile.currentAddress:
                addr_dict = profile.currentAddress.copy()
                if isinstance(addr_dict, dict) and addr_dict.get("formatted"):
                    all_addresses.append((broker, "current", addr_dict))

            # Previous addresses
            if hasattr(profile, "previousAddresses") and profile.previousAddresses:
                for addr in profile.previousAddresses:
                    if isinstance(addr, dict) and addr.get("formatted"):
                        all_addresses.append((broker, "previous", addr))

        # Deduplicate by similarity
        unique_addresses = []
        seen_formatted = set()

        for broker, addr_type, addr_dict in all_addresses:
            formatted = addr_dict.get("formatted", "").strip()

            if not formatted:
                continue

            # Check similarity with existing addresses
            is_duplicate = False
            for seen_addr in seen_formatted:
                similarity = self._string_similarity(formatted, seen_addr)
                if similarity >= self.ADDRESS_SIMILARITY_THRESHOLD:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_addresses.append(addr_dict)
                seen_formatted.add(formatted)

        logger.debug(
            f"Consolidated addresses: {len(unique_addresses)} unique "
            f"(from {len(all_addresses)} raw)"
        )

        # First address is primary, rest are previous
        if unique_addresses:
            return unique_addresses[0], unique_addresses[1:]
        else:
            return {}, []

    def _consolidate_relatives(
        self, profiles: Dict[str, Profile]
    ) -> List[Dict[str, str]]:
        """
        Extract and deduplicate relatives from all profiles.

        Args:
            profiles: Dict of broker profiles

        Returns:
            List of unique relatives
        """
        relatives_dict = {}  # name -> relative_info

        for broker, profile in profiles.items():
            if not profile or not hasattr(profile, "relatives"):
                continue

            for relative in profile.relatives:
                if isinstance(relative, dict) and relative.get("name"):
                    name = relative["name"].strip().lower()
                    if name not in relatives_dict:
                        relatives_dict[name] = relative

        relatives_list = list(relatives_dict.values())
        logger.debug(f"Consolidated {len(relatives_list)} unique relatives")
        return relatives_list[:10]  # Limit to top 10

    def _consolidate_associates(
        self, profiles: Dict[str, Profile]
    ) -> List[Dict[str, str]]:
        """
        Extract and deduplicate associates from all profiles.

        Args:
            profiles: Dict of broker profiles

        Returns:
            List of unique associates
        """
        associates_dict = {}  # name -> associate_info

        for broker, profile in profiles.items():
            if not profile or not hasattr(profile, "associates"):
                continue

            for associate in profile.associates:
                if isinstance(associate, dict) and associate.get("name"):
                    name = associate["name"].strip().lower()
                    if name not in associates_dict:
                        associates_dict[name] = associate

        associates_list = list(associates_dict.values())
        logger.debug(f"Consolidated {len(associates_list)} unique associates")
        return associates_list[:10]  # Limit to top 10

    def _consolidate_properties(
        self, profiles: Dict[str, Profile]
    ) -> List[Dict[str, Any]]:
        """
        Extract and deduplicate properties from all profiles.

        Args:
            profiles: Dict of broker profiles

        Returns:
            List of unique properties
        """
        properties_dict = {}  # address -> property_info

        for broker, profile in profiles.items():
            if not profile or not hasattr(profile, "properties"):
                continue

            for prop in profile.properties:
                if isinstance(prop, dict) and prop.get("address"):
                    addr = prop["address"].strip().lower()
                    if addr not in properties_dict:
                        properties_dict[addr] = prop

        properties_list = list(properties_dict.values())
        logger.debug(f"Consolidated {len(properties_list)} unique properties")
        return properties_list[:10]  # Limit to top 10

    @staticmethod
    def _string_similarity(str1: str, str2: str) -> float:
        """
        Calculate string similarity (0-1).

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0-1)
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def main():
    """Test profile consolidator"""
    from targets.fps.models import Profile

    # Create mock profiles
    fps_profile = Profile(
        profileId="fps_1",
        fullName="James Oehring",
        age=61,
        currentAddress={"formatted": "413 Lovers Ln, Cameron, MO 64429"},
        phoneNumbers=[{"number": "(816) 225-8592"}],
        emailAddresses=["james@example.com"],
        relatives=[{"name": "Rickilinda Oehring", "relationship": "family"}],
    )

    npd_profile = Profile(
        profileId="npd_1",
        fullName="James Oehring",
        age=61,
        currentAddress={"formatted": "413 Lovers Lane, Cameron, Missouri 64429"},
        phoneNumbers=[{"number": "(816) 225-8592"}, {"number": "(816) 632-2218"}],
        emailAddresses=["james.oehring@gmail.com"],
        relatives=[{"name": "Rickilinda Oehring", "relationship": "spouse"}],
    )

    profiles = {"fps": fps_profile, "npd": npd_profile}

    # Test consolidation
    consolidator = ProfileConsolidator()
    consolidated = consolidator.consolidate(
        profiles,
        person_id="person_123",
        confidence=75.2,
        enrichment_data={
            "services_found": ["github", "linkedin"],
            "breaches": [{"name": "LinkedIn 2021", "date": 1623265200}],
        },
    )

    print("✅ Consolidated Profile:")
    print(f"   Name: {consolidated.full_name}")
    print(f"   Age: {consolidated.age}")
    print(f"   Phones: {consolidated.phone_numbers}")
    print(f"   Emails: {consolidated.emails}")
    print(f"   Primary Address: {consolidated.primary_address}")
    print(f"   Relatives: {len(consolidated.relatives)}")
    print(f"   Services: {consolidated.services_found}")
    print(f"   Breaches: {len(consolidated.breaches)}")
    print(f"   Sources: {consolidated.sources}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
