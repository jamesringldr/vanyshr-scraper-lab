#!/usr/bin/env python3
"""
Phase 2 End-to-End Test

Tests full flow:
1. Run Phase 1 (summary scraping + deduplication)
2. Select top dedup group
3. Run Phase 2 (full profiles + enrichment)
4. Display consolidated results
"""

import asyncio
import logging
import os
import json

from sequence_runner import SequenceRunner
from data_models import QuickScanInput

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def test_phase2_end_to_end():
    """Run full Phase 1 + Phase 2 test"""

    # Initialize runner
    runner = SequenceRunner()

    # Test input
    user_input = QuickScanInput(
        first_name="James",
        last_name="Oehring",
        city="Cameron",
        state="MO"
    )

    print("\n" + "=" * 80)
    print("PHASE 2 END-TO-END TEST: James Oehring, Cameron, MO")
    print("=" * 80)

    # ============================================================================
    # PHASE 1: Summary scraping + deduplication
    # ============================================================================
    print("\n[PHASE 1] Running summary scraping and deduplication...")

    phase1_output = await runner.quickscan(user_input)

    print(f"\n✅ Phase 1 Complete!")
    print(f"   Total Time: {phase1_output.metadata['total_time_ms']}ms")
    print(f"   Profiles Found: {len(phase1_output.dedup_groups)}")
    print(f"   Raw Summaries: {sum(len(r.summaries) for r in phase1_output.raw_results.values())}")
    print()

    # Display Phase 1 results
    for i, group in enumerate(phase1_output.dedup_groups, 1):
        display = group.to_display()
        print(f"Profile {i}:")
        print(f"  Name: {display['name']}")
        print(f"  Age: {display['age']}")
        print(f"  Location: {display.get('city', '')}, {display.get('state', '')}")
        print(f"  Sources: {', '.join(display['sources'])}")
        print(f"  Confidence: {display['confidence']}%")
        if display.get('age_note'):
            print(f"  Note: {display['age_note']}")
        print()

    # ============================================================================
    # PHASE 2: Full profiles + enrichment
    # ============================================================================
    if not phase1_output.dedup_groups:
        print("❌ No dedup groups found, skipping Phase 2")
        return

    # Select top dedup group (highest confidence)
    selected_group = phase1_output.dedup_groups[0]

    print("\n" + "=" * 80)
    print(f"[PHASE 2] Running full profile scraping and enrichment...")
    print(f"Selected: {selected_group.primary_name} (Confidence: {selected_group.average_confidence:.1f}%)")
    print("=" * 80)
    print()

    # Check if we have profile URLs
    has_profile_urls = any(m.summary.profile_url for m in selected_group.members)

    if not has_profile_urls:
        print("⚠️  No profile URLs found in dedup group members")
        print("Available members:")
        for member in selected_group.members:
            print(f"  - {member.summary.broker.value}: {member.summary.full_name}")
            print(f"    URL: {member.summary.profile_url}")
        print()
        print("Note: FPS/NPD/AnyWho may need the profile URL from search results")
        return

    try:
        consolidated_profile = await runner.full_profile_phase(
            selected_group, user_input
        )

        if not consolidated_profile:
            print("❌ Phase 2 failed - no consolidated profile returned")
            return

        # ========================================================================
        # Display Phase 2 Results
        # ========================================================================
        print("\n✅ Phase 2 Complete!")
        print()
        print("CONSOLIDATED PROFILE:")
        print(f"  Name: {consolidated_profile.full_name}")
        print(f"  Age: {consolidated_profile.age}")
        print(f"  Confidence: {consolidated_profile.confidence:.1f}%")
        print(f"  Sources: {', '.join(consolidated_profile.sources)}")
        print()

        print("CONTACT INFORMATION (Deduplicated):")
        if consolidated_profile.primary_address:
            print(f"  Primary Address: {consolidated_profile.primary_address.get('formatted', 'N/A')}")
        if consolidated_profile.previous_addresses:
            print(f"  Previous Addresses: {len(consolidated_profile.previous_addresses)}")
            for addr in consolidated_profile.previous_addresses[:3]:
                print(f"    - {addr.get('formatted', 'N/A')}")

        print()
        print(f"  Phone Numbers ({len(consolidated_profile.phone_numbers)}):")
        for phone in consolidated_profile.phone_numbers:
            print(f"    - {phone}")

        print()
        print(f"  Email Addresses ({len(consolidated_profile.emails)}):")
        for email in consolidated_profile.emails:
            print(f"    - {email}")

        print()
        print("FAMILY & RELATIONS:")
        if consolidated_profile.relatives:
            print(f"  Relatives ({len(consolidated_profile.relatives)}):")
            for rel in consolidated_profile.relatives[:5]:
                print(f"    - {rel.get('name', 'Unknown')}")
        else:
            print("  No relatives found")

        if consolidated_profile.associates:
            print(f"  Associates ({len(consolidated_profile.associates)}):")
            for assoc in consolidated_profile.associates[:5]:
                print(f"    - {assoc.get('name', 'Unknown')}")

        print()
        print("ENRICHMENT DATA:")
        if consolidated_profile.services_found:
            print(f"  Online Services ({len(consolidated_profile.services_found)}):")
            for service in consolidated_profile.services_found:
                print(f"    - {service}")
        else:
            print("  No online services found")

        if consolidated_profile.breaches:
            print(f"  Data Breaches ({len(consolidated_profile.breaches)}):")
            for breach in consolidated_profile.breaches[:5]:
                breach_name = breach.get('name', 'Unknown')
                breach_date = breach.get('date', 'Unknown')
                print(f"    - {breach_name} ({breach_date})")
        else:
            print("  No data breaches found")

        print()
        print("PROFILE DATA SOURCES:")
        for broker, profile in consolidated_profile.raw_profiles.items():
            emails = len(profile.emailAddresses) if hasattr(profile, 'emailAddresses') else 0
            phones = len(profile.phoneNumbers) if hasattr(profile, 'phoneNumbers') else 0
            print(f"  {broker.upper()}: {emails} emails, {phones} phones")

        print()
        print("=" * 80)
        print("✅ PHASE 2 TEST COMPLETE")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Phase 2 failed with error: {e}", exc_info=True)
        print(f"❌ Phase 2 failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_phase2_end_to_end())
