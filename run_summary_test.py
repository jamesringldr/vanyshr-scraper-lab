#!/usr/bin/env python3
"""
Run the Phase 1 summary scrapers (FPS, NPD, AnyWho, Zaba) against the test
profiles and write a results CSV for manual accuracy review.

Output columns follow the established results layout: a SUMMARY row per person
carrying timing and counts, then one DETAIL row per result per broker.

Rows are written and flushed as each profile completes, so interrupting a run
keeps everything already fetched. Per-broker timings print inline, which is how
a slow broker becomes visible while the sweep is running.

Usage:
    python3 run_summary_test.py                 # first 5 profiles
    python3 run_summary_test.py --limit 17      # all of them
    python3 run_summary_test.py --only oehring,clark
    python3 run_summary_test.py --timeout 10    # tighter per-scraper bound
    python3 run_summary_test.py --out /tmp/results.csv

Long sweeps are worth backgrounding so progress stays visible and the run can
be stopped without losing work.
"""

import argparse
import asyncio
import csv
import sys
import time
from pathlib import Path

from sequence_runner import SequenceRunner
from data_models import QuickScanInput

REPO_ROOT = Path(__file__).parent
DEFAULT_INPUT = REPO_ROOT / "context" / "summary- test_profiles.csv"
DEFAULT_OUTPUT = REPO_ROOT / "context" / "summary_results_test_profiles.csv"

# Phase 1 summary brokers
BROKERS = ("fps", "npd", "anywho", "zaba")

# Per-scraper timeout. A profile takes as long as its slowest broker, so this
# is also the per-profile worst case. SequenceRunner defaults to 60s, which let
# a 17-profile sweep run 9 minutes; observed healthy calls finish in 0.4-4s.
DEFAULT_TIMEOUT = 20

FIELDNAMES = [
    "search_ID", "profile_number", "target", "first_name", "last_name",
    "city", "state_id", "age", "response_time_s", "brokers_searched",
    "total_results", "notes", "address", "phones", "emails", "aliases",
    "relatives",
]


def load_profiles(path):
    with open(path, newline="") as f:
        return [
            {k: (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(f)
        ]


def blank_row(profile, **overrides):
    """A row with every column present, so the CSV never shifts."""
    row = {name: "" for name in FIELDNAMES}
    row.update(
        search_ID=profile["search_ID"],
        first_name=profile["first_name"],
        last_name=profile["last_name"],
        city=profile["city"],
        state_id=profile["state_id"],
    )
    row.update(overrides)
    return row


def age_of(summary):
    """FPS supplies an int age; NPD and AnyWho supply a string ageRange."""
    return str(summary.age) if summary.age else (summary.age_range or "")


async def run(profiles, runner, writer, flush):
    """
    Run each profile, writing its rows before starting the next one.

    Rows are flushed per profile rather than collected and written at the end:
    a sweep is minutes of paid API calls, and an interrupted run that discards
    everything it already fetched is the worst possible failure. Killing this
    mid-run leaves a valid CSV of the profiles that finished.
    """
    written = 0

    for i, profile in enumerate(profiles, 1):
        label = profile["search_ID"]
        print(f"{i:2}/{len(profiles)} {label:<12}", end=" ", flush=True)
        started = time.time()
        rows = []

        try:
            output = await runner.quickscan(
                QuickScanInput(
                    first_name=profile["first_name"],
                    last_name=profile["last_name"],
                    city=profile["city"],
                    state=profile["state_id"],
                )
            )
        except Exception as e:
            elapsed = time.time() - started
            print(f"✗ {elapsed:5.1f}s  {type(e).__name__}: {str(e)[:50]}")
            writer.writerow(blank_row(
                profile,
                profile_number="ERROR",
                target="ALL",
                response_time_s=f"{elapsed:.2f}",
                notes=str(e)[:200],
            ))
            flush()
            written += 1
            continue

        elapsed = time.time() - started
        scraped = {b: r for b, r in output.raw_results.items() if b.lower() in BROKERS}
        total = sum(len(r.summaries) for r in scraped.values())

        rows.append(blank_row(
            profile,
            profile_number="SUMMARY",
            target="ALL",
            response_time_s=f"{elapsed:.2f}",
            brokers_searched=len([r for r in scraped.values() if r.status != "failed"]),
            total_results=total,
            notes="Summary row with timing",
        ))

        for broker, result in scraped.items():
            broker = broker.lower()
            timing = f"{result.timing_ms / 1000:.2f}"

            if result.status != "success" or not result.summaries:
                rows.append(blank_row(
                    profile,
                    profile_number="NO_RESULTS",
                    target=broker,
                    response_time_s=timing,
                    # Keep the whole URL visible -- for NPD the 404'd URL is the
                    # useful part when judging coverage vs a URL-format problem.
                    notes=f"Status: {result.status}"
                          + (f" ({result.error[:300]})" if result.error else ""),
                ))
                continue

            for n, summary in enumerate(result.summaries, 1):
                name_parts = summary.full_name.split()
                rows.append(blank_row(
                    profile,
                    profile_number=n,
                    target=broker,
                    # Name as the broker returned it, not as searched -- this is
                    # how wrong-person matches become visible on review.
                    first_name=name_parts[0] if name_parts else "",
                    last_name=name_parts[-1] if len(name_parts) > 1 else "",
                    age=age_of(summary),
                    response_time_s=timing,
                    notes=f"Profile {n} from {broker}",
                    address=summary.address,
                    phones=summary.phone,
                    emails=summary.email,
                    aliases=summary.aliases,
                    relatives=summary.relatives,
                ))

        writer.writerows(rows)
        flush()
        written += len(rows)

        # Per-broker timings inline, so a slow broker is visible while the
        # sweep runs rather than only in the CSV afterwards.
        slowest = sorted(scraped.items(), key=lambda kv: -kv[1].timing_ms)
        detail = " ".join(f"{b.lower()[:3]}:{r.timing_ms/1000:.1f}" for b, r in slowest)
        print(f"✓ {elapsed:5.1f}s  {total:>2} results   {detail}")

    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="how many profiles (default 5)")
    parser.add_argument("--only", help="comma-separated search_IDs to run instead")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"per-scraper timeout in seconds (default {DEFAULT_TIMEOUT}). "
             "A profile takes as long as its slowest broker, so this bounds "
             "the per-profile worst case",
    )
    args = parser.parse_args()

    profiles = load_profiles(args.input)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        profiles = [p for p in profiles if p["search_ID"] in wanted]
    else:
        profiles = profiles[: args.limit]

    print(f"Testing {len(profiles)} profile(s) across {', '.join(BROKERS).upper()}")
    print(f"Timeout {args.timeout}s per scraper -> worst case ~{args.timeout}s per profile")
    print(f"Writing to {args.out} as each profile completes\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()

    # Opened before the run and flushed per profile, so an interrupted sweep
    # keeps what it already fetched.
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        f.flush()

        try:
            written = asyncio.run(
                run(profiles, SequenceRunner(timeout=args.timeout), writer, f.flush)
            )
        except KeyboardInterrupt:
            print(f"\n⚠️  interrupted — rows already written are intact in {args.out}")
            return 130

    print(f"\n✅ {written} rows in {time.time() - started:.0f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
