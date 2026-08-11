#!/usr/bin/env python3
"""Test AnyWho scraper with real data."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from targets.anywho.scraper import AnyWhoScraper

TEST_QUERIES = [
    ("James", "Oehring", "Cameron", "MO"),
    ("John", "Smith", "New York", "NY"),
    ("Mary", "Johnson", "Los Angeles", "CA"),
]

def test_scraper():
    if not os.environ.get("CONTEXT_DEV_API_KEY"):
        print("❌ No API key")
        return False

    try:
        scraper = AnyWhoScraper(timeout=60)
        print("✅ Initialized AnyWhoScraper\n")
    except Exception as e:
        print(f"❌ Init failed: {e}")
        return False

    results = []
    for i, (first, last, city, state) in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] {first} {last}, {city}, {state}")
        try:
            output = scraper.run({"firstName": first, "lastName": last, "city": city, "state": state, "timeout": 60})
            print(f"  Status: {output.status}, Time: {output.execution_time_ms}ms")
            if output.summary_results:
                print(f"  Summaries: {len(output.summary_results)}")
            if output.profile:
                print(f"  Profile: {output.profile.fullName}")
            results.append(output.status in ("success", "no_results"))
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:80]}")
            results.append(False)

    print("\n" + "=" * 80)
    print(f"✅ Successful: {sum(results)}/{len(results)}")
    return all(results)

if __name__ == "__main__":
    success = test_scraper()
    sys.exit(0 if success else 1)
