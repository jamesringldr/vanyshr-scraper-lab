#!/usr/bin/env python3
"""
Unit tests for Zaba scraper (no external API calls).

Tests:
- URL building
- Multiple profile extraction
- Model conversion
- Error handling
"""

import sys
from pathlib import Path
from dataclasses import asdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from targets.zaba.scraper import ZabaScraper, ScraperParams
from targets.zaba.models import ScrapeOutput


def test_url_building():
    """Test URL building for Zaba"""
    print("\n" + "=" * 80)
    print("Test: URL Building")
    print("=" * 80)

    scraper = ZabaScraper.__new__(ZabaScraper)  # Create without init to avoid API key check
    scraper.timeout = 60

    test_cases = [
        (("James", "Oehring", "Cameron", "MO"),
         "https://search.zaba.com/s?q=James+Oehring&where=Cameron,+mo"),
        (("John", "Smith", "New York", "NY"),
         "https://search.zaba.com/s?q=John+Smith&where=New+York,+ny"),
        (("Mary", "Johnson", "Los Angeles", "CA"),
         "https://search.zaba.com/s?q=Mary+Johnson&where=Los+Angeles,+ca"),
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

    scraper = ZabaScraper.__new__(ZabaScraper)

    test_cases = [
        ("61", 61),
        ("DOB: 1963", 63),
        ("Age 62", 62),
        ("37 years old", 37),
        (None, None),
        ("", None),
    ]

    for input_val, expected in test_cases:
        result = scraper._parse_age(input_val)
        # Allow ±2 year variance for DOB calculations
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


def test_multiple_profile_extraction():
    """Test extracting multiple profiles from single page"""
    print("\n" + "=" * 80)
    print("Test: Multiple Profile Extraction")
    print("=" * 80)

    scraper = ZabaScraper.__new__(ZabaScraper)

    # Mock data from context.dev Extract (multiple results)
    test_data = {
        "results": [
            {
                "name": "James Oehring",
                "age": "61",
                "address": "413 Lovers Ln, Cameron, MO 64429",
                "phone": ["(816) 555-0123"],
                "email": ["james@example.com"],
                "relatives": ["John Oehring", "Jane Oehring"],
                "associates": [],
                "properties": ["413 Lovers Ln, Cameron, MO 64429"]
            },
            {
                "name": "James A Oehring",
                "age": "88",
                "address": "900 Main St, Kansas City, MO",
                "phone": ["(816) 555-0456"],
                "email": [],
                "relatives": ["James Oehring"],
                "associates": ["Bob Smith"],
                "properties": []
            },
            {
                "name": "James R Oehring",
                "age": "42",
                "address": "500 Oak Ave, Springfield, MO",
                "phone": [],
                "email": ["j.oehring@work.com"],
                "relatives": [],
                "associates": [],
                "properties": ["500 Oak Ave, Springfield, MO"]
            }
        ]
    }

    profiles = scraper._extract_profiles(test_data)

    print(f"✅ Extracted {len(profiles)} profiles")
    assert len(profiles) == 3, f"Expected 3 profiles, got {len(profiles)}"

    # Check first profile
    p1 = profiles[0]
    print(f"   [1] {p1.fullName}: age={p1.age}, phones={len(p1.phoneNumbers)}, relatives={len(p1.relatives)}")
    assert p1.fullName == "James Oehring"
    assert p1.age == 61
    assert len(p1.phoneNumbers) == 1
    assert len(p1.emailAddresses) == 1
    assert len(p1.relatives) == 2

    # Check second profile
    p2 = profiles[1]
    print(f"   [2] {p2.fullName}: age={p2.age}, phones={len(p2.phoneNumbers)}, associates={len(p2.associates)}")
    assert p2.fullName == "James A Oehring"
    assert len(p2.associates) == 1

    # Check third profile
    p3 = profiles[2]
    print(f"   [3] {p3.fullName}: age={p3.age}, emails={len(p3.emailAddresses)}")
    assert p3.fullName == "James R Oehring"
    assert len(p3.emailAddresses) == 1

    print("\n✅ Multiple profile extraction test passed!")
    return True


def test_empty_data_handling():
    """Test handling of empty/missing data"""
    print("\n" + "=" * 80)
    print("Test: Empty Data Handling")
    print("=" * 80)

    scraper = ZabaScraper.__new__(ZabaScraper)

    # Empty data
    profiles = scraper._extract_profiles({})
    print(f"✅ Empty dict → {len(profiles)} profiles")
    assert len(profiles) == 0

    # No results
    profiles = scraper._extract_profiles({"results": []})
    print(f"✅ No results → {len(profiles)} profiles")
    assert len(profiles) == 0

    # Results without names (should be filtered)
    profiles = scraper._extract_profiles({
        "results": [
            {"age": "61", "address": "123 Main"},
            {"name": "John Smith", "age": "30"}
        ]
    })
    print(f"✅ Mixed valid/invalid → {len(profiles)} profiles")
    assert len(profiles) == 1
    assert profiles[0].fullName == "John Smith"

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
    print("Zaba Scraper - Unit Tests (No External API)")
    print("=" * 80)

    tests = [
        test_scraper_params,
        test_url_building,
        test_age_parsing,
        test_multiple_profile_extraction,
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
