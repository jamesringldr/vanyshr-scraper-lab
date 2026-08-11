#!/usr/bin/env python3
"""
Unit tests for FPS scraper (no external API calls).

Tests:
- URL building
- Data extraction and model conversion
- Error handling
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import asdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from targets.fps.scraper import FPSScraper, ScraperParams
from targets.fps.models import ScrapeOutput


def test_url_building():
    """Test URL building"""
    print("\n" + "=" * 80)
    print("Test: URL Building")
    print("=" * 80)

    scraper = FPSScraper.__new__(FPSScraper)  # Create without init to avoid API key check
    scraper.timeout = 10

    test_cases = [
        (("James", "Oehring", "Cameron", "MO"),
         "https://www.fastpeoplesearch.com/name/james-oehring_cameron-mo"),
        (("John", "Smith", "New York", "NY"),
         "https://www.fastpeoplesearch.com/name/john-smith_new-york-ny"),
        (("Mary", "Johnson", "Los Angeles", "CA"),
         "https://www.fastpeoplesearch.com/name/mary-johnson_los-angeles-ca"),
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
    """Test age parsing"""
    print("\n" + "=" * 80)
    print("Test: Age Parsing")
    print("=" * 80)

    scraper = FPSScraper.__new__(FPSScraper)

    test_cases = [
        ("61", 61),
        ("Age 62", 62),
        ("37 years old", 37),
        ("Age range 50-60", 50),
        (None, None),
        ("", None),
        ("no age", None),
    ]

    for input_val, expected in test_cases:
        result = scraper._parse_age(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} Input: {repr(input_val):20} → {result} (expected {expected})")
        if result != expected:
            return False

    print("\n✅ All age parsing tests passed!")
    return True


def test_summary_extraction():
    """Test summary result extraction"""
    print("\n" + "=" * 80)
    print("Test: Summary Result Extraction")
    print("=" * 80)

    scraper = FPSScraper.__new__(FPSScraper)

    # Mock data from context.dev Extract
    test_data = {
        "name": "James Oehring",
        "age": "61",
        "address": "Cameron, MO",
        "phone": "(123) 456-7890",
        "email": "james@example.com",
        "relatives": ["John Oehring", "Jane Oehring"],
        "previous_addresses": ["123 Main St, Cameron, MO", "456 Oak Ave, Cameron, MO"]
    }

    results = scraper._extract_summary_results(test_data)

    print(f"✅ Extracted {len(results)} summary result(s)")
    if results:
        r = results[0]
        print(f"   Name: {r.fullName}")
        print(f"   Address: {r.address}")
        print(f"   Age: {r.age}")
        print(f"   Phone: {r.phone}")
        print(f"   Result ID: {r.resultId}")

        # Validate
        assert r.fullName == "James Oehring", "Name mismatch"
        assert r.address == "Cameron, MO", "Address mismatch"
        assert r.age == 61, "Age mismatch"
        assert r.phone == "(123) 456-7890", "Phone mismatch"

    print("\n✅ Summary extraction test passed!")
    return True


def test_profile_extraction():
    """Test profile extraction"""
    print("\n" + "=" * 80)
    print("Test: Profile Extraction")
    print("=" * 80)

    scraper = FPSScraper.__new__(FPSScraper)

    # Mock data from context.dev Extract
    test_data = {
        "name": "James Oehring",
        "age": "61",
        "address": "413 Lovers Ln, Cameron, MO 64429",
        "phone": "(123) 456-7890",
        "email": "james@example.com",
        "relatives": ["John Oehring", "Jane Oehring"],
        "previous_addresses": ["123 Main St, Cameron, MO", "456 Oak Ave, Cameron, MO"]
    }

    profile = scraper._extract_profile(test_data)

    print(f"✅ Extracted profile: {profile.fullName}")
    print(f"   Age: {profile.age}")
    print(f"   Current Address: {profile.currentAddress.get('formatted')}")
    print(f"   Previous Addresses: {len(profile.previousAddresses)}")
    print(f"   Phone Numbers: {len(profile.phoneNumbers)}")
    print(f"   Email Addresses: {len(profile.emailAddresses)}")
    print(f"   Relatives: {len(profile.relatives)}")

    # Validate
    assert profile.fullName == "James Oehring", "Name mismatch"
    assert profile.age == 61, "Age mismatch"
    assert len(profile.previousAddresses) == 2, f"Expected 2 prev addresses, got {len(profile.previousAddresses)}"
    assert len(profile.relatives) == 2, f"Expected 2 relatives, got {len(profile.relatives)}"
    assert len(profile.phoneNumbers) == 1, f"Expected 1 phone, got {len(profile.phoneNumbers)}"

    print("\n✅ Profile extraction test passed!")
    return True


def test_empty_data_handling():
    """Test handling of empty/missing data"""
    print("\n" + "=" * 80)
    print("Test: Empty Data Handling")
    print("=" * 80)

    scraper = FPSScraper.__new__(FPSScraper)

    # Empty data
    results = scraper._extract_summary_results({})
    profile = scraper._extract_profile({})

    print(f"✅ Empty dict → {len(results)} results, profile={profile}")
    assert len(results) == 0, "Should return empty list for empty dict"
    assert profile is None, "Should return None for empty dict"

    # Missing name (required field)
    results = scraper._extract_summary_results({"age": "61", "address": "Cameron, MO"})
    profile = scraper._extract_profile({"age": "61", "address": "Cameron, MO"})

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
        assert params.timeout == 10, "Default timeout should be 10"
        print(f"✅ Default timeout: {params.timeout}")

        # Test with custom timeout
        params2 = ScraperParams(
            firstName="John",
            lastName="Smith",
            city="New York",
            state="NY",
            timeout=30
        )
        assert params2.timeout == 30, "Custom timeout should be 30"
        print(f"✅ Custom timeout: {params2.timeout}")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print("\n✅ Parameter validation test passed!")
    return True


def run_all_tests():
    """Run all unit tests"""
    print("\n" + "=" * 80)
    print("FPS Scraper - Unit Tests (No External API)")
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
