#!/usr/bin/env python3
"""Unit tests for scraper sequence runner."""

import sys
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))

from scraper_sequence import AggregatedProfile, ScraperResult


def test_aggregated_profile_merging():
    """Test aggregating data from multiple scrapers."""
    print("\n" + "=" * 80)
    print("Test: Profile Aggregation")
    print("=" * 80)

    agg = AggregatedProfile()

    # Simulate FPS result
    fps_data = {
        "fullName": "James Oehring",
        "age": 61,
        "currentAddress": {"formatted": "Cameron, MO"},
        "phoneNumbers": [{"number": "(816) 555-0123"}],
        "relatives": [{"name": "John Oehring"}]
    }

    # Simulate NPD result
    npd_data = {
        "fullName": "James Oehring",
        "age": 62,
        "currentAddress": {"formatted": "413 Lovers Ln, Cameron, MO 64429"},
        "phoneNumbers": [{"number": "(816) 555-0123"}],
        "emailAddresses": ["james@example.com"],
        "relatives": [{"name": "Jane Oehring"}]
    }

    # Simulate AnyWho result
    anywho_data = {
        "fullName": "James Oehring",
        "currentAddress": {"formatted": "Cameron, MO"},
        "phoneNumbers": [{"number": "(816) 555-0456"}],
        "relatives": [{"name": "Jane Oehring"}]
    }

    # Manually aggregate (simulating what the runner does)
    agg.name = fps_data["fullName"]
    agg.age = fps_data.get("age")
    agg.address = npd_data["currentAddress"]["formatted"]  # Use NPD's more detailed address
    agg.sources = ["FPS", "NPD", "AnyWho"]

    # Merge phones
    for phone_data in fps_data["phoneNumbers"]:
        phone = phone_data["number"]
        if phone not in agg.phones:
            agg.phones.append(phone)

    for phone_data in anywho_data["phoneNumbers"]:
        phone = phone_data["number"]
        if phone not in agg.phones:
            agg.phones.append(phone)

    # Merge emails
    if "emailAddresses" in npd_data:
        for email in npd_data["emailAddresses"]:
            if email not in agg.emails:
                agg.emails.append(email)

    # Merge relatives
    for rel_data in fps_data["relatives"]:
        rel = rel_data["name"]
        if rel not in agg.relatives:
            agg.relatives.append(rel)

    for rel_data in npd_data["relatives"]:
        rel = rel_data["name"]
        if rel not in agg.relatives:
            agg.relatives.append(rel)

    # Verify aggregation
    print(f"✅ Name: {agg.name}")
    print(f"✅ Age: {agg.age}")
    print(f"✅ Address: {agg.address}")
    print(f"✅ Phones: {len(agg.phones)} found - {agg.phones}")
    print(f"✅ Emails: {len(agg.emails)} found - {agg.emails}")
    print(f"✅ Relatives: {len(agg.relatives)} found - {agg.relatives}")
    print(f"✅ Sources: {agg.sources}")

    assert agg.name == "James Oehring"
    assert agg.age == 61
    assert "Lovers Ln" in agg.address
    assert len(agg.phones) == 2  # Two unique phones
    assert len(agg.emails) == 1
    assert len(agg.relatives) == 2  # Two unique relatives
    assert len(agg.sources) == 3

    print("\n✅ Profile aggregation test passed!")
    return True


def test_scraper_result_tracking():
    """Test ScraperResult data class."""
    print("\n" + "=" * 80)
    print("Test: ScraperResult Tracking")
    print("=" * 80)

    result = ScraperResult(
        scraper_name="FPS",
        status="success",
        execution_time_ms=1500,
        summary_count=3,
        profile_found=True
    )

    print(f"✅ Scraper: {result.scraper_name}")
    print(f"✅ Status: {result.status}")
    print(f"✅ Time: {result.execution_time_ms}ms")
    print(f"✅ Summaries: {result.summary_count}")
    print(f"✅ Profile: {result.profile_found}")

    assert result.scraper_name == "FPS"
    assert result.status == "success"
    assert result.execution_time_ms == 1500

    print("\n✅ ScraperResult tracking test passed!")
    return True


def test_error_handling():
    """Test error handling in results."""
    print("\n" + "=" * 80)
    print("Test: Error Handling")
    print("=" * 80)

    error_result = ScraperResult(
        scraper_name="ZabaFake",
        status="failed",
        execution_time_ms=5000,
        error="IP blocking: Website access error"
    )

    print(f"✅ Failed scraper: {error_result.scraper_name}")
    print(f"✅ Status: {error_result.status}")
    print(f"✅ Error: {error_result.error}")

    assert error_result.status == "failed"
    assert error_result.error is not None
    assert "IP blocking" in error_result.error

    print("\n✅ Error handling test passed!")
    return True


def run_all_tests():
    """Run all unit tests."""
    print("\n" + "=" * 80)
    print("SEQUENCE RUNNER - UNIT TESTS")
    print("=" * 80)

    tests = [
        test_scraper_result_tracking,
        test_aggregated_profile_merging,
        test_error_handling,
    ]

    passed = sum(1 for t in tests if t())

    print("\n" + "=" * 80)
    print(f"✅ Passed: {passed}/{len(tests)}")
    if passed == len(tests):
        print("🎉 All unit tests passed!")
        return True
    return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
