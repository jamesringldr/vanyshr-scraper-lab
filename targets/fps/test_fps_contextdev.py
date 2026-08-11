#!/usr/bin/env python3
"""
Test FPS scraper with context.dev Extract API.

Tests the scraper against multiple queries to validate:
- URL building
- Data extraction
- Model output format
- Error handling
"""

import sys
import os
import json
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from targets.fps.scraper import FPSScraper

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
    """Test FPS scraper with multiple queries"""

    print_header("FPS Scraper - Context.dev Extract Testing")

    # Check API key
    if not os.environ.get("CONTEXT_DEV_API_KEY"):
        print("❌ ERROR: CONTEXT_DEV_API_KEY environment variable not set")
        return False

    try:
        scraper = FPSScraper(timeout=30)
        print(f"✅ Initialized FPSScraper with context.dev API")
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
                "timeout": 30
            }

            # Build URL for reference
            import re
            fn = first.lower()
            ln = last.lower()
            c = city.lower().replace(" ", "-")
            s = state.lower()
            url = f"https://www.fastpeoplesearch.com/name/{fn}-{ln}_{c}-{s}"
            print(f"URL: {url}")

            # Run scraper
            output = scraper.run(params)

            # Check results
            print(f"Status: {output.status}")
            print(f"Time: {output.execution_time_ms}ms")

            if output.summary_results:
                print(f"✅ Summary Results: {len(output.summary_results)} found")
                for j, result in enumerate(output.summary_results):
                    print(f"   [{j+1}] {result.fullName}")
                    if result.address:
                        print(f"       Address: {result.address}")
                    if result.age:
                        print(f"       Age: {result.age}")
                    if result.phone:
                        print(f"       Phone: {result.phone}")
            else:
                print(f"⚠️  No summary results")

            if output.profile:
                print(f"✅ Profile: {output.profile.fullName}")
                if output.profile.currentAddress.get("formatted"):
                    print(f"   Address: {output.profile.currentAddress['formatted']}")
                if output.profile.relatives:
                    print(f"   Relatives: {len(output.profile.relatives)}")
                if output.profile.previousAddresses:
                    print(f"   Previous Addresses: {len(output.profile.previousAddresses)}")
            else:
                print(f"⚠️  No profile data")

            if output.error:
                print(f"⚠️  Error: {output.error}")

            results.append({
                "query": query_name,
                "status": output.status,
                "time_ms": output.execution_time_ms,
                "summary_count": len(output.summary_results),
                "has_profile": output.profile is not None,
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
        print(f"{symbol} {r['query']:<40} {status}")

    if successful == len(results):
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n⚠️  {len(results) - successful} test(s) failed")
        return False


if __name__ == "__main__":
    success = test_scraper()
    sys.exit(0 if success else 1)
