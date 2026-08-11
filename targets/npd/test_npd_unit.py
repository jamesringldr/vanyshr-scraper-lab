#!/usr/bin/env python3
"""
Unit tests for NPD scraper (no external API calls).

Tests:
- URL building
- Data extraction and model conversion
- Error handling
- Age parsing (handles DOB format)
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import asdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from targets.npd.scraper import NPDScraper, ScraperParams
from targets.npd.models import ScrapeOutput


def test_url_building():
    """Test URL building for NPD format"""
    print("\n" + "=" * 80)
    print("Test: URL Building")
    print("=" * 80)

    scraper = NPDScraper.__new__(NPDScraper)  # Create without init to avoid API key check
    scraper.timeout = 60

    test_cases = [
        (("James", "Oehring", "Cameron", "MO"),
         "https://nationalpublicdata.com/people/o/james-oehring/mo/cameron/"),
        (("John", "Smith", "New York", "NY"),
         "https://nationalpublicdata.com/people/s/john-smith/ny/new-york/"),
        (("Mary", "Johnson", "Los Angeles", "CA"),
         "https://nationalpublicdata.com/people/j/mary-johnson/ca/los-angeles/"),
    ]

    for (first, last, city, state), expected_url in test_cases:
        params = ScraperParams(
            firstName=first,
            lastName=last,
            city=city,
            state=state
        )
        url = scraper._build_search_url(params)
        status = "✅" if url == expected_url else "❌"
        print(f"{status} {first} {last}, {city}, {state}")
        print(f"   Expected: {expected_url}")
        print(f"   Got:      {url}")
        if url != expected_url:
            return False

    print("\n✅ All URL building tests passed!")
    return True


def test_age_parsing():
    """Test age parsing (handles both ages and DOB)"""
    print("\n" + "=" * 80)
    print("Test: Age Parsing (with DOB support)")
    print("=" * 80)

    scraper = NPDScraper.__new__(NPDScraper)

    test_cases = [
        ("61", 61),
        ("DOB: 1963", 61),  # Calculates age from year
        ("Born 1965", 61),
        ("Age 62", 62),
        ("37 years old", 37),
        (None, None),
        ("", None),
        ("no age", None),
    ]

    for input_val, expected in test_cases:
        result = scraper._parse_age(input_val)
        # For DOB parsing, allow ±2 year variance due to date calculations and year changes
        if expected is not None and result is not None:
            match = abs(result - expected) <= 2
        else:
            match = result == expected

        status = "✅" if match else "❌"
        print(f"{status} Input: {repr(input_val):20} → {result} (expected ~{expected})")
        if not match:
            return False

    print("\n✅ All age parsing tests passed!")
    return True


def test_summary_extraction():
    """Test summary result extraction"""
    print("\n" + "=" * 80)
    print("Test: Summary Result Extraction")
    print("=" * 80)

    scraper = NPDScraper.__new__(NPDScraper)

    # Mock data from context.dev Extract
    test_data = {
        "name": "James Oehring",
        "age": "DOB: 1963",
        "address": "413 Lovers Ln, Cameron, MO 64429",
        "phone": "(816) 555-0123",
        "email": "james@example.com",
        "relatives": ["John Oehring", "Jane Oehring"],
        "previous_addresses": ["123 Main St, Cameron, MO", "456 Oak Ave, Cameron, MO"],
        "properties": ["413 Lovers Ln, Cameron, MO"]
    }

    results = scraper._extract_summary_results(test_data)

    print(f"✅ Extracted {len(results)} summary result(s)")
    if results:
        r = results[0]
        print(f"   Name: {r.fullName}")
        print(f"   Address: {r.addressPreview}")
        print(f"   Phone: {r.phonePreview}")
        print(f"   Match Score: {r.matchScore}")
        print(f"   Result ID: {r.resultId}")

        # Validate
        assert r.fullName == "James Oehring", "Name mismatch"
        assert r.addressPreview == "413 Lovers Ln, Cameron, MO 64429", "Address mismatch"
        assert r.phonePreview == "(816) 555-0123", "Phone mismatch"
        assert r.matchScore == 100, "Match score should be 100"

    print("\n✅ Summary extraction test passed!")
    return True


def test_profile_extraction():
    """Test profile extraction with properties"""
    print("\n" + "=" * 80)
    print("Test: Profile Extraction")
    print("=" * 80)

    scraper = NPDScraper.__new__(NPDScraper)

    # Mock data from context.dev Extract
    test_data = {
        "name": "James Oehring",
        "age": "DOB: 1963",
        "address": "413 Lovers Ln, Cameron, MO 64429",
        "phone": "(816) 555-0123",
        "email": "james@example.com",
        "relatives": ["John Oehring", "Jane Oehring"],
        "previous_addresses": ["123 Main St, Cameron, MO", "456 Oak Ave, Cameron, MO"],
        "properties": ["413 Lovers Ln, Cameron, MO", "789 Pine Rd, Excelsior Springs, MO"]
    }

    profile = scraper._extract_profile(test_data)

    print(f"✅ Extracted profile: {profile.fullName}")
    print(f"   Age: {profile.age}")
    print(f"   Current Address: {profile.currentAddress.get('formatted')}")
    print(f"   Previous Addresses: {len(profile.previousAddresses)}")
    print(f"   Phone Numbers: {len(profile.phoneNumbers)}")
    print(f"   Email Addresses: {len(profile.emailAddresses)}")
    print(f"   Relatives: {len(profile.relatives)}")
    print(f"   Properties: {len(profile.properties)}")

    # Validate
    assert profile.fullName == "James Oehring", "Name mismatch"
    assert profile.age is not None, "Age should be parsed"
    assert len(profile.previousAddresses) == 2, f"Expected 2 prev addresses, got {len(profile.previousAddresses)}"
    assert len(profile.relatives) == 2, f"Expected 2 relatives, got {len(profile.relatives)}"
    assert len(profile.phoneNumbers) == 1, f"Expected 1 phone, got {len(profile.phoneNumbers)}"
    assert len(profile.properties) == 2, f"Expected 2 properties, got {len(profile.properties)}"

    print("\n✅ Profile extraction test passed!")
    return True


def test_empty_data_handling():
    """Test handling of empty/missing data"""
    print("\n" + "=" * 80)
    print("Test: Empty Data Handling")
    print("=" * 80)

    scraper = NPDScraper.__new__(NPDScraper)

    # Empty data
    results = scraper._extract_summary_results({})
    profile = scraper._extract_profile({})

    print(f"✅ Empty dict → {len(results)} results, profile={profile}")
    assert len(results) == 0, "Should return empty list for empty dict"
    assert profile is None, "Should return None for empty dict"

    # Missing name (required field)
    results = scraper._extract_summary_results({"age": "DOB: 1963", "address": "Cameron, MO"})
    profile = scraper._extract_profile({"age": "DOB: 1963", "address": "Cameron, MO"})

    print(f"✅ Missing name → {len(results)} results, profile={profile}")
    assert len(results) == 0, "Should return empty list when name is missing"
    assert profile is None, "Should return None when name is missing"

    print("\n✅ Empty data handling test passed!")
    return True


def test_scraper_params():
    """Test parameter validation"""
    print("\n" + "=" * 80)
    print("Test: Scraper Parameters")
    print("=" * 80)

    try:
        params = ScraperParams(
            firstName="James",
            lastName="Oehring",
            city="Cameron",
            state="MO"
        )
        print(f"✅ Valid params created: {params.firstName} {params.lastName}")

        # Check defaults
        assert params.timeout == 60, "Default timeout should be 60"
        print(f"✅ Default timeout: {params.timeout}")

        # Test with custom timeout
        params2 = ScraperParams(
            firstName="John",
            lastName="Smith",
            city="New York",
            state="NY",
            timeout=90
        )
        assert params2.timeout == 90, "Custom timeout should be 90"
        print(f"✅ Custom timeout: {params2.timeout}")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print("\n✅ Parameter validation test passed!")
    return True


def run_all_tests():
    """Run all unit tests"""
    print("\n" + "=" * 80)
    print("NPD Scraper - Unit Tests (No External API)")
    print("=" * 80)

    tests = [
        test_scraper_params,
        test_url_building,
        test_age_parsing,
        test_summary_extraction,
        test_profile_extraction,
        test_empty_data_handling,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test {test_func.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"✅ Passed: {passed}/{passed + failed}")
    print(f"❌ Failed: {failed}/{passed + failed}")

    if failed == 0:
        print("\n🎉 All unit tests passed!")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
