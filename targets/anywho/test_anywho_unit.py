#!/usr/bin/env python3
"""Unit tests for AnyWho scraper."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from targets.anywho.scraper import AnyWhoScraper, ScraperParams


def test_url_building():
    """Test URL building for AnyWho"""
    print("\n" + "=" * 80)
    print("Test: URL Building")
    print("=" * 80)

    scraper = AnyWhoScraper.__new__(AnyWhoScraper)
    scraper.timeout = 60

    test_cases = [
        (("James", "Oehring", "Cameron", "MO"),
         "https://www.anywho.com/people/james+oehring/missouri/cameron"),
        (("John", "Smith", "New York", "NY"),
         "https://www.anywho.com/people/john+smith/new-york/new-york"),
        (("Mary", "Johnson", "Los Angeles", "CA"),
         "https://www.anywho.com/people/mary+johnson/california/los-angeles"),
    ]

    for (first, last, city, state), expected_url in test_cases:
        params = ScraperParams(firstName=first, lastName=last, city=city, state=state)
        url = scraper._build_search_url(params)
        status = "✅" if url == expected_url else "❌"
        print(f"{status} {first} {last}, {city}, {state}")
        if url != expected_url:
            print(f"   Expected: {expected_url}")
            print(f"   Got:      {url}")
            return False

    print("\n✅ All URL building tests passed!")
    return True


def test_extract_summary():
    """Test summary extraction"""
    print("\n" + "=" * 80)
    print("Test: Summary Extraction")
    print("=" * 80)

    scraper = AnyWhoScraper.__new__(AnyWhoScraper)

    test_data = {
        "results": [
            {
                "name": "James Oehring",
                "address": "Cameron, MO",
                "age_range": "60-70",
                "location": "Cameron, MO",
                "profile_url": "https://www.anywho.com/..."
            },
            {
                "name": "James A Oehring",
                "address": "Kansas City, MO",
                "age_range": "80-90",
                "location": "Kansas City, MO",
                "profile_url": "https://www.anywho.com/..."
            }
        ]
    }

    results = scraper._extract_summary_results(test_data)
    print(f"✅ Extracted {len(results)} summary results")
    assert len(results) == 2
    assert results[0].fullName == "James Oehring"

    print("\n✅ Summary extraction test passed!")
    return True


def test_profile_extraction():
    """Test profile extraction"""
    print("\n" + "=" * 80)
    print("Test: Profile Extraction")
    print("=" * 80)

    scraper = AnyWhoScraper.__new__(AnyWhoScraper)

    test_data = {
        "name": "James Oehring",
        "age": "61",
        "address": "413 Lovers Ln, Cameron, MO 64429",
        "phone": ["(816) 555-0123"],
        "email": ["james@example.com"],
        "family_members": ["John Oehring", "Jane Oehring"],
        "properties": ["413 Lovers Ln, Cameron, MO"]
    }

    profile = scraper._extract_profile(test_data)
    print(f"✅ Extracted profile: {profile.fullName}")
    print(f"   Phones: {len(profile.phoneNumbers)}, Emails: {len(profile.emailAddresses)}")
    assert profile.fullName == "James Oehring"
    assert len(profile.phoneNumbers) == 1
    assert len(profile.familyMembers) == 2

    print("\n✅ Profile extraction test passed!")
    return True


def test_all():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("AnyWho Scraper - Unit Tests")
    print("=" * 80)

    tests = [test_url_building, test_extract_summary, test_profile_extraction]
    passed = sum(1 for t in tests if t())

    print("\n" + "=" * 80)
    print(f"✅ Passed: {passed}/{len(tests)}")
    if passed == len(tests):
        print("🎉 All unit tests passed!")
        return True
    return False


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
