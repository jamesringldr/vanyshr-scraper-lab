#!/usr/bin/env python3
"""
Email Extractor

Consolidates emails from multiple broker profiles into a single deduplicated set.
Used before Holehe enrichment to find which services a person uses.
"""

import logging
import re
from typing import Set, Dict, List, Any

from targets.fps.models import Profile

logger = logging.getLogger(__name__)


class EmailExtractor:
    """Extracts and deduplicates emails from broker profiles"""

    # Common email patterns to filter out (not real user emails)
    EXCLUDE_PATTERNS = [
        r"noreply@",
        r"no-reply@",
        r"notifications@",
        r"alerts@",
        r"automail@",
        r"test@",
        r"example@",
        r"admin@fastpeoplesearch",
        r"admin@anywho",
        r"admin@zabasearch",
        r"admin@nationalpublicdata",
    ]

    def extract_from_profiles(self, profiles: Dict[str, Profile]) -> Set[str]:
        """
        Extract all emails from a collection of broker profiles.

        Args:
            profiles: Dict of {broker_name: Profile}
                e.g., {'fps': Profile(...), 'npd': Profile(...), ...}

        Returns:
            Deduplicated set of email addresses
        """
        emails = set()

        for broker_name, profile in profiles.items():
            if not profile or not isinstance(profile, Profile):
                continue

            if hasattr(profile, "emailAddresses") and profile.emailAddresses:
                for email in profile.emailAddresses:
                    if email and isinstance(email, str):
                        email = email.lower().strip()

                        # Validate email format
                        if self._is_valid_email(email):
                            # Check against exclusion patterns
                            if not self._should_exclude(email):
                                emails.add(email)
                                logger.debug(
                                    f"Found email from {broker_name}: {email}"
                                )
                            else:
                                logger.debug(
                                    f"Excluded email from {broker_name}: {email}"
                                )

        logger.info(f"Extracted {len(emails)} unique emails from {len(profiles)} profiles")
        return emails

    def extract_from_consolidated(
        self, consolidated_data: Dict[str, Any]
    ) -> Set[str]:
        """
        Extract emails from consolidated profile data.

        Args:
            consolidated_data: Dict with 'raw_profiles' or 'emails' key

        Returns:
            Deduplicated set of email addresses
        """
        emails = set()

        # If already consolidated with emails field
        if "emails" in consolidated_data:
            for email in consolidated_data.get("emails", []):
                if self._is_valid_email(email):
                    emails.add(email.lower())

        # If raw profiles are available
        if "raw_profiles" in consolidated_data:
            profiles = consolidated_data["raw_profiles"]
            if isinstance(profiles, dict):
                emails.update(self.extract_from_profiles(profiles))

        return emails

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validate email format"""
        if not email or not isinstance(email, str):
            return False

        # Basic email regex
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _should_exclude(self, email: str) -> bool:
        """Check if email should be excluded"""
        email_lower = email.lower()

        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, email_lower):
                return True

        return False

    def deduplicate_emails(self, email_list: List[str]) -> Set[str]:
        """
        Deduplicate a list of emails.

        Args:
            email_list: List of email addresses (may have duplicates)

        Returns:
            Deduplicated set of valid emails
        """
        emails = set()

        for email in email_list:
            if email and self._is_valid_email(email):
                emails.add(email.lower().strip())

        return emails


def main():
    """Test email extractor"""
    from targets.fps.models import Profile

    # Create mock profiles with emails
    fps_profile = Profile(
        profileId="fps_1",
        fullName="James Oehring",
        emailAddresses=["james@example.com", "james.oehring@gmail.com"],
    )

    npd_profile = Profile(
        profileId="npd_1",
        fullName="James Oehring",
        emailAddresses=["james@example.com", "j.oehring@yahoo.com"],
    )

    anywho_profile = Profile(
        profileId="anywho_1",
        fullName="James Oehring",
        emailAddresses=["james@example.com"],  # Duplicate
    )

    profiles = {
        "fps": fps_profile,
        "npd": npd_profile,
        "anywho": anywho_profile,
    }

    extractor = EmailExtractor()
    emails = extractor.extract_from_profiles(profiles)

    print(f"✅ Extracted emails: {emails}")
    print(f"   Total unique emails: {len(emails)}")
    for email in sorted(emails):
        print(f"   - {email}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
