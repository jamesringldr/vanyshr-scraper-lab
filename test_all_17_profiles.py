#!/usr/bin/env python3
"""
Full test of 17 test profiles across FPS, NPD, AnyWho brokers.
Outputs CSV with SUMMARY rows (timing/metadata) and DETAIL rows (actual results).
For manual accuracy validation.
"""

import asyncio
import csv
import time
from pathlib import Path
from sequence_runner import SequenceRunner
from data_models import QuickScanInput

# Read all test profiles
test_profiles = []
with open("/Users/jameso/Downloads/Test Profiles - test_profiles (1).csv", 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        test_profiles.append({
            'search_ID': row['search_ID'].strip(),
            'first_name': row['first_name'].strip(),
            'last_name': row['last_name'].strip(),
            'city': row['city'].strip(),
            'state_id': row['state_id'].strip(),
        })

print(f"📋 Testing {len(test_profiles)} profiles")
print(f"   Across 3 brokers (FPS, NPD, AnyWho)")
print(f"   ~{len(test_profiles) * 3 * 3}+ API calls, ETA: 3-5 minutes\n")

runner = SequenceRunner()
csv_rows = []

async def run_tests():
    for i, profile in enumerate(test_profiles, 1):
        search_id = profile['search_ID']
        first_name = profile['first_name']
        last_name = profile['last_name']
        city = profile['city']
        state = profile['state_id']

        start_time = time.time()
        print(f"{i:2}. Testing {search_id:<12}", end=" ", flush=True)

        try:
            # Run Phase 1
            user_input = QuickScanInput(
                first_name=first_name,
                last_name=last_name,
                city=city,
                state=state
            )

            output = await runner.quickscan(user_input)
            elapsed = time.time() - start_time

            # Count total results across all brokers
            total_results = sum(len(r.summaries) for r in output.raw_results.values())

            # SUMMARY ROW
            csv_rows.append({
                'search_ID': search_id,
                'profile_number': 'SUMMARY',
                'target': 'ALL',
                'first_name': first_name,
                'last_name': last_name,
                'city': city,
                'state_id': state,
                'response_time_s': f"{elapsed:.2f}",
                'brokers_searched': len([r for r in output.raw_results.values() if r.status != 'failed']),
                'total_results': total_results,
                'notes': 'Summary row with timing',
                # Empty detail fields
                'age': '',
                'address': '',
                'phones': '',
                'emails': '',
                'aliases': '',
                'relatives': ''
            })

            # DETAIL ROWS - One per result per broker
            for broker_name, scrape_result in output.raw_results.items():
                broker_lower = broker_name.lower()
                if broker_lower == 'zaba':
                    continue

                # Handle 404 or error case
                if scrape_result.status != 'success' or not scrape_result.summaries:
                    csv_rows.append({
                        'search_ID': search_id,
                        'profile_number': 'NO_RESULTS',
                        'target': broker_lower,
                        'first_name': first_name,
                        'last_name': last_name,
                        'city': city,
                        'state_id': state,
                        'response_time_s': f"{scrape_result.timing_ms/1000:.2f}",
                        'brokers_searched': '',
                        'total_results': '',
                        'notes': f"Status: {scrape_result.status}",
                        'age': '',
                        'address': '',
                        'phones': '',
                        'emails': '',
                        'aliases': ''
                    })
                else:
                    # Add row for each result found
                    for profile_num, summary in enumerate(scrape_result.summaries, 1):
                        # Extract age if available
                        age_str = ""
                        if summary.age:
                            age_str = str(summary.age)
                        elif summary.age_range:
                            age_str = str(summary.age_range)

                        # Extract optional fields (phones, emails, aliases, relatives)
                        phones_str = getattr(summary, 'phones', '') or getattr(summary, 'phone', '') or ''
                        emails_str = getattr(summary, 'emails', '') or getattr(summary, 'email', '') or ''
                        aliases_str = getattr(summary, 'aliases', '') or ''
                        relatives_str = getattr(summary, 'relatives', '') or ''

                        csv_rows.append({
                            'search_ID': search_id,
                            'profile_number': profile_num,
                            'target': broker_lower,
                            'first_name': summary.full_name.split()[0] if ' ' in summary.full_name else summary.full_name,
                            'last_name': summary.full_name.split()[-1] if ' ' in summary.full_name else '',
                            'city': city,
                            'state_id': state,
                            'response_time_s': f"{scrape_result.timing_ms/1000:.2f}",
                            'brokers_searched': '',
                            'total_results': '',
                            'notes': f"Profile {profile_num} from {broker_lower}",
                            'age': age_str,
                            'address': summary.address,
                            'phones': phones_str,
                            'emails': emails_str,
                            'aliases': aliases_str,
                            'relatives': relatives_str
                        })

            print(f"✓ ({elapsed:.1f}s, {total_results} results)")

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)[:100]
            print(f"✗ ({error_msg})")

            csv_rows.append({
                'search_ID': search_id,
                'profile_number': 'ERROR',
                'target': 'ALL',
                'first_name': first_name,
                'last_name': last_name,
                'city': city,
                'state_id': state,
                'response_time_s': f"{elapsed:.2f}",
                'brokers_searched': '',
                'total_results': '',
                'notes': error_msg,
                'age': '',
                'address': '',
                'phones': '',
                'emails': '',
                'aliases': ''
            })

# Run all tests
asyncio.run(run_tests())

# Write CSV
output_file = "/Users/jameso/Downloads/Test_Profiles_-_detailed_results.csv"
with open(output_file, 'w', newline='') as f:
    fieldnames = [
        'search_ID', 'profile_number', 'target', 'first_name', 'last_name',
        'city', 'state_id', 'response_time_s', 'brokers_searched', 'total_results',
        'notes', 'age', 'address', 'phones', 'emails', 'aliases', 'relatives'
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in csv_rows:
        writer.writerow(row)

print(f"\n✅ Test complete!")
print(f"   Rows generated: {len(csv_rows)}")
print(f"   Output file: {output_file}")
