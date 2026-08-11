#!/usr/bin/env python3
"""
Test Zaba scraper with context.dev Extract API.

Tests the scraper against multiple queries to validate:
- URL building
- Multiple profile extraction
- Model output format
- Error handling
"""

import sys
import os
import json
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from targets.zaba.scraper import ZabaScraper

# Test queries: (first_name, last_name, city, state)
TEST_QUERIES = [
    ("James", "Oehring", "Cameron", "MO"),
    ("John", "Smith", "New York", "NY"),
    ("Mary", "Johnson", "Los Angeles", "CA"),
    ("Robert", "Williams", "Chicago", "IL"),
    ("Patricia", "Brown", "Houston", "TX"),
]


def print_header(text):
    """Print section header"""
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print('=' * 80)


def test_scraper():
    """Test Zaba scraper with multiple queries"""

    print_header("Zaba Scraper - Context.dev Extract Testing")

    # Check API key
    if not os.environ.get("CONTEXT_DEV_API_KEY"):
        print("❌ ERROR: CONTEXT_DEV_API_KEY environment variable not set")
        return False

    try:
        scraper = ZabaScraper(timeout=60)
        print(f"✅ Initialized ZabaScraper with context.dev API")
    except Exception as e:
        print(f"❌ Failed to initialize scraper: {e}")
        return False

    results = []

    for i, (first, last, city, state) in enumerate(TEST_QUERIES, 1):
        query_name = f"{first} {last}, {city}, {state}"
        print(f"\n[{i}/{len(TEST_QUERIES)}] Testing: {query_name}")
        print("-" * 80)

        try:
            params = {
                "firstName": first,
                "lastName": last,
                "city": city,
                "state": state,
                "timeout": 60
            }

            # Build URL for reference
            url = f"https://search.zaba.com/s?q={first}+{last}&where={city},+{state.lower()}"
            print(f"URL: {url}")

            # Run scraper
            output = scraper.run(params)

            # Check results
            print(f"Status: {output.status}")
            print(f"Time: {output.execution_time_ms}ms")

            if output.profiles:
                print(f"✅ Profiles Found: {len(output.profiles)}")
                for j, profile in enumerate(output.profiles[:3]):  # Show first 3
                    print(f"   [{j+1}] {profile.fullName}")
                    if profile.currentAddress.get("formatted"):
                        print(f"       Address: {profile.currentAddress['formatted']}")
                    if profile.age:
                        print(f"       Age: {profile.age}")
                    if profile.phoneNumbers:
                        print(f"       Phones: {len(profile.phoneNumbers)}")
                    if profile.relatives:
                        print(f"       Relatives: {len(profile.relatives)}")

                if len(output.profiles) > 3:
                    print(f"   ... and {len(output.profiles) - 3} more")
            else:
                print(f"⚠️  No profiles found")

            if output.error:
                print(f"⚠️  Error: {output.error}")

            results.append({
                "query": query_name,
                "status": output.status,
                "time_ms": output.execution_time_ms,
                "profile_count": len(output.profiles),
                "success": output.status == "success" or output.status == "no_results"
            })

        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "query": query_name,
                "status": "error",
                "error": str(e),
                "success": False
            })

    # Summary
    print_header("Test Summary")

    successful = sum(1 for r in results if r["success"])
    print(f"\n✅ Successful: {successful}/{len(results)}")

    for r in results:
        symbol = "✅" if r["success"] else "❌"
        status = r.get("status", "error")
        profiles = r.get("profile_count", 0)
        print(f"{symbol} {r['query']:<40} {status} ({profiles} profiles)")

    if successful == len(results):
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n⚠️  {len(results) - successful} test(s) failed")
        return False


if __name__ == "__main__":
    success = test_scraper()
    sys.exit(0 if success else 1)
