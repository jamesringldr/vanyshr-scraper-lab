#!/usr/bin/env python3
"""
Run the Phase 1 summary scrapers (FPS, NPD, AnyWho, Zaba) against test
subjects pulled from testing.test_subjects and log results to
testing.scrape_runs / testing.summary_results, plus a CSV for quick eyeballing.

Subjects come from the DB (--group selects full/core/quick/me, matching
test_subjects.test_group) rather than a static CSV -- testing.test_subjects is
the source of truth now, seeded and maintained directly in Supabase.

Rows are written and flushed as each profile completes, so interrupting a run
keeps everything already fetched -- both the CSV and what's already committed
to the DB. Per-broker timings print inline, which is how a slow broker
becomes visible while the sweep is running.

Usage:
    python3 run_summary_test.py                  # --group quick (5 profiles)
    python3 run_summary_test.py --group core      # 15 profiles
    python3 run_summary_test.py --group full      # everyone
    python3 run_summary_test.py --group me
    python3 run_summary_test.py --only chris.ocker,lucas.clark
    python3 run_summary_test.py --timeout 10      # tighter per-scraper bound
    python3 run_summary_test.py --out /tmp/results.csv

Long sweeps are worth backgrounding so progress stays visible and the run can
be stopped without losing work.
"""

import argparse
import asyncio
import csv
import subprocess
import sys
import time
from pathlib import Path

import db
from sequence_runner import SequenceRunner
from data_models import QuickScanInput

REPO_ROOT = Path(__file__).parent
DEFAULT_OUTPUT = REPO_ROOT / "context" / "summary_results_test_profiles.csv"

# Phase 1 summary brokers
BROKERS = ("fps", "npd", "anywho", "zaba")

# Per-scraper timeout. A profile takes as long as its slowest broker, so this
# is also the per-profile worst case. SequenceRunner defaults to 60s, which let
# a 17-profile sweep run 9 minutes; observed healthy calls finish in 0.4-4s.
DEFAULT_TIMEOUT = 20

FIELDNAMES = [
    "subject_id", "profile_number", "target", "first_name", "last_name",
    "city", "state_id", "age", "response_time_s", "brokers_searched",
    "total_results", "notes", "address", "phones", "emails", "aliases",
    "relatives",
]


def git_ref() -> str:
    """Best-effort branch/commit label for the run's notes; never worth
    failing the sweep over."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def blank_row(profile, **overrides):
    """A row with every column present, so the CSV never shifts."""
    row = {name: "" for name in FIELDNAMES}
    row.update(
        subject_id=profile["id"],
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


async def run(profiles, runner, run_pk, writer, flush):
    """
    Run each profile, writing its rows (CSV and DB) before starting the next.

    Rows are flushed per profile rather than collected and written at the end:
    a sweep is minutes of paid API calls, and an interrupted run that discards
    everything it already fetched is the worst possible failure. Killing this
    mid-run leaves a valid CSV, and a DB run, of the profiles that finished.
    """
    written = 0

    for i, profile in enumerate(profiles, 1):
        label = profile["id"]
        print(f"{i:2}/{len(profiles)} {label:<20}", end=" ", flush=True)
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
            # Not written to the DB: summary_results.target is constrained to
            # actual brokers (fps/npd/anywho/zaba), and a whole-quickscan
            # failure has no per-broker breakdown to attribute it to. The CSV
            # row above is the record of this one.
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

        db_rows = []

        for broker, result in scraped.items():
            broker = broker.lower()
            timing = f"{result.timing_ms / 1000:.2f}"

            if result.status != "success" or not result.summaries:
                notes = f"Status: {result.status}" + (f" ({result.error[:300]})" if result.error else "")
                rows.append(blank_row(
                    profile,
                    profile_number="NO_RESULTS",
                    target=broker,
                    response_time_s=timing,
                    # Keep the whole URL visible -- for NPD the 404'd URL is the
                    # useful part when judging coverage vs a URL-format problem.
                    notes=notes,
                ))
                db_rows.append({
                    "target": broker,
                    "status": result.status,
                    "response_time_ms": round(result.timing_ms),
                    "notes": notes,
                })
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
                db_rows.append({
                    "target": broker,
                    "status": "success",
                    "response_time_ms": round(result.timing_ms),
                    "full_name": summary.full_name,
                    "address": summary.address,
                    "age": summary.age,
                    "profile_url": summary.profile_url,
                    "notes": f"Profile {n} from {broker}",
                    "raw": summary.to_dict(),
                })

        writer.writerows(rows)
        flush()
        written += len(rows)

        db.insert_summary_results(run_pk, profile["id"], db_rows)

        # Per-broker timings inline, so a slow broker is visible while the
        # sweep runs rather than only in the CSV afterwards.
        slowest = sorted(scraped.items(), key=lambda kv: -kv[1].timing_ms)
        detail = " ".join(f"{b.lower()[:3]}:{r.timing_ms/1000:.1f}" for b, r in slowest)
        print(f"✓ {elapsed:5.1f}s  {total:>2} results   {detail}")

    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--group", default="quick", choices=["full", "core", "quick", "me"],
        help="test_subjects.test_group to run (default quick)",
    )
    parser.add_argument("--limit", type=int, help="cap the number of profiles run")
    parser.add_argument("--only", help="comma-separated subject ids to run instead, e.g. chris.ocker,lucas.clark")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"per-scraper timeout in seconds (default {DEFAULT_TIMEOUT}). "
             "A profile takes as long as its slowest broker, so this bounds "
             "the per-profile worst case",
    )
    args = parser.parse_args()

    db.require_configured()

    profiles = db.fetch_subjects(args.group)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        profiles = [p for p in profiles if p["id"] in wanted]
    if args.limit:
        profiles = profiles[: args.limit]

    if not profiles:
        sys.exit(f"No test_subjects found for group={args.group!r} (or --only matched nothing)")

    print(f"Testing {len(profiles)} profile(s) [group={args.group}] across {', '.join(BROKERS).upper()}")
    print(f"Timeout {args.timeout}s per scraper -> worst case ~{args.timeout}s per profile")
    print(f"Writing to {args.out} as each profile completes\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    run_pk = db.start_run(git_ref=git_ref(), notes=f"group={args.group} limit={args.limit}")

    # Opened before the run and flushed per profile, so an interrupted sweep
    # keeps what it already fetched.
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        f.flush()

        try:
            written = asyncio.run(
                run(profiles, SequenceRunner(timeout=args.timeout), run_pk, writer, f.flush)
            )
        except KeyboardInterrupt:
            print(f"\n⚠️  interrupted — rows already written are intact in {args.out} and testing.summary_results")
            db.finish_run(run_pk)
            return 130

    db.finish_run(run_pk)
    print(f"\n✅ {written} rows in {time.time() - started:.0f}s -> {args.out} and testing.summary_results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
