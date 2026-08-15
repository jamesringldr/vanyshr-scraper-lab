#!/usr/bin/env python3
"""
Run Phase 2 full-profile scrapers (FPS, NPD, AnyWho, Zaba) against confirmed
matches -- testing.summary_results rows with is_target_match = true -- and
log results to testing.scrape_runs / testing.full_profile_results.

Zaba has no per-person profile URL to follow like the other three, so it's
re-searched by name/city instead of fetched by URL. It's a genuine re-scrape,
not a passthrough of the Phase 1 summary row: sequence_runner.py caches
Zaba's full Profile object (richer than the SummaryResult Phase 1 keeps --
adds aliases, past addresses, county) in memory for reuse within a single
quickscan() call, but that cache never reaches the DB and this script is a
separate process running later, so there's nothing to reuse here.

Only subjects with at least one is_target_match = true row are scraped --
run whatever set is_target_match first (see JOURNAL.md).

Usage:
    python3 run_full_profile_test.py --only james.oehring
    python3 run_full_profile_test.py --group quick
    python3 run_full_profile_test.py --group full --limit 5 --offset 5
"""

import argparse
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import db
from fps_full_profile_scraper import FPSFullProfileScraper
from npd_full_profile_scraper import NPDFullProfileScraper
from anywho_full_profile_scraper import AnyWhoFullProfileScraper
from zaba_html_scraper import ZabaHtmlScraper

REPO_ROOT = Path(__file__).parent
DEFAULT_TIMEOUT = 20


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


def flatten_profile(profile) -> dict:
    """
    Broker Profile dataclasses (targets/*/models.py) share most of their
    shape, with per-broker exceptions:
    - relatives (FPS/NPD/Zaba) vs familyMembers (AnyWho)
    - previousAddresses (FPS/NPD/AnyWho) vs pastAddresses (Zaba)
    - aliases (Zaba only)
    - property_* (FPS only) -- from the `properties` list
    - county can come from `properties` (FPS) or nested in currentAddress
      (Zaba, which has no separate property section but does report county)
    Anything a given broker doesn't carry is None, which is expected, not a
    gap -- see the migrations that added these columns for which broker
    has which.
    """
    d = asdict(profile)
    relatives = d.get("relatives") or d.get("familyMembers") or []
    associates = d.get("associates") or []
    previous = d.get("previousAddresses") or d.get("pastAddresses") or []
    properties = (d.get("properties") or [{}])[0]
    current_address = d.get("currentAddress") or {}
    aliases = d.get("aliases")  # Zaba: List[str]; other brokers don't have this field at all

    return {
        "full_name": d.get("fullName") or None,
        "age": d.get("age"),
        "date_of_birth": d.get("dateOfBirth"),
        "current_address": current_address.get("formatted", ""),
        "previous_addresses": "; ".join(a.get("formatted", "") for a in previous if a.get("formatted")),
        "phone": ", ".join(p.get("number", "") for p in (d.get("phoneNumbers") or []) if p.get("number")),
        "email": ", ".join(d.get("emailAddresses") or []),
        "relatives": ", ".join(r.get("name", "") for r in relatives if r.get("name")),
        "aliases": ", ".join(aliases) if aliases else None,
        "associates": ", ".join(a.get("name", "") for a in associates if a.get("name")),
        "resided_since": properties.get("residedSince"),
        "property_beds": properties.get("beds"),
        "property_baths": properties.get("baths"),
        "property_sqft": properties.get("squareFeet"),
        "property_year_built": properties.get("yearBuilt"),
        "property_estimated_value": properties.get("estimatedValue"),
        "property_county": properties.get("county") or current_address.get("county"),
        "raw": d,
    }


def pick_zaba_profile(profiles, confirmed):
    """
    Zaba is re-searched by name/city rather than fetched by a stable URL, so
    the right person has to be re-identified among however many candidates
    come back this time -- same disambiguation problem update_target_match
    solved for Phase 1, at smaller scale (Zaba rarely returns more than one
    or two candidates).
    """
    if not profiles:
        return None
    if len(profiles) == 1:
        return profiles[0]

    def norm(name):
        parts = (name or "").strip().lower().split()
        return f"{parts[0]} {parts[-1]}" if len(parts) >= 2 else (name or "").strip().lower()

    target_name = norm(confirmed["full_name"])
    candidates = [p for p in profiles if norm(p.fullName) == target_name]
    if len(candidates) == 1:
        return candidates[0]

    target_addr = (confirmed["address"] or "").strip().lower()
    for p in candidates or profiles:
        if (p.currentAddress.get("formatted") or "").strip().lower() == target_addr:
            return p

    return candidates[0] if candidates else None


def scrape_url_based(target, scraper, m):
    """FPS/NPD/AnyWho: fetch the confirmed profile_url directly."""
    started = time.time()
    try:
        profile = scraper.scrape_profile(m["profile_url"], profile_id=str(m["summary_result_id"]))
    except Exception as e:
        return {
            "target": target,
            "summary_result_id": m["summary_result_id"],
            "status": "failed",
            "response_time_ms": round((time.time() - started) * 1000),
            "notes": f"{type(e).__name__}: {str(e)[:200]}",
        }

    elapsed_ms = round((time.time() - started) * 1000)
    if not profile:
        return {
            "target": target,
            "summary_result_id": m["summary_result_id"],
            "status": "failed",
            "response_time_ms": elapsed_ms,
            "notes": "scraper returned no profile",
        }

    return {
        "target": target,
        "summary_result_id": m["summary_result_id"],
        "status": "success",
        "response_time_ms": elapsed_ms,
        **flatten_profile(profile),
    }


def scrape_zaba(scraper, m, subject):
    """
    Zaba has no per-person URL -- re-search by name/city and pick the
    candidate matching the confirmed Phase 1 result. This is a real
    re-scrape, not a passthrough; see the module docstring for why.
    """
    started = time.time()
    try:
        output = scraper.run({
            "firstName": subject["first_name"],
            "lastName": subject["last_name"],
            "city": subject["city"],
            "state": subject["state_id"],
        })
    except Exception as e:
        return {
            "target": "zaba",
            "summary_result_id": m["summary_result_id"],
            "status": "failed",
            "response_time_ms": round((time.time() - started) * 1000),
            "notes": f"{type(e).__name__}: {str(e)[:200]}",
        }

    elapsed_ms = round((time.time() - started) * 1000)
    profile = pick_zaba_profile(getattr(output, "profiles", None) or [], m)
    if not profile:
        return {
            "target": "zaba",
            "summary_result_id": m["summary_result_id"],
            "status": "failed",
            "response_time_ms": elapsed_ms,
            "notes": "no matching candidate in the re-scraped results",
        }

    return {
        "target": "zaba",
        "summary_result_id": m["summary_result_id"],
        "status": "success",
        "response_time_ms": elapsed_ms,
        **flatten_profile(profile),
    }


def run(subject_ids, scrapers, notes):
    run_pk = db.start_run(git_ref=git_ref(), notes=notes, kind="fullprofile")
    written = 0

    for subject_id in subject_ids:
        matches = db.fetch_confirmed_matches([subject_id])
        if not matches:
            print(f"{subject_id:20} no confirmed matches -- skipping")
            continue

        subject = db.fetch_subject(subject_id)
        print(f"{subject_id:20}", end=" ", flush=True)
        rows = []

        for m in matches:
            target = m["target"]
            if target == "zaba":
                rows.append(scrape_zaba(scrapers["zaba"], m, subject))
                continue

            scraper = scrapers.get(target)
            if not scraper:
                continue
            rows.append(scrape_url_based(target, scraper, m))

        db.insert_full_profile_results(run_pk, subject_id, rows)
        written += len(rows)
        detail = " ".join(f"{r['target']}:{r['status']}" for r in rows)
        print(f"✓ {detail}")

    db.finish_run(run_pk)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=["full", "core", "quick", "me"])
    parser.add_argument("--only", help="comma-separated subject ids, e.g. chris.ocker,lucas.clark")
    parser.add_argument("--limit", type=int, help="cap the number of subjects run")
    parser.add_argument("--offset", type=int, default=0, help="skip this many subjects first, for running a group in batches")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Zaba re-scrape timeout in seconds (default {DEFAULT_TIMEOUT})")
    args = parser.parse_args()

    db.require_configured()

    if args.only:
        subject_ids = [s.strip() for s in args.only.split(",")]
    elif args.group:
        subject_ids = [p["id"] for p in db.fetch_subjects(args.group)]
    else:
        sys.exit("Specify --group or --only")

    if args.offset:
        subject_ids = subject_ids[args.offset:]
    if args.limit:
        subject_ids = subject_ids[: args.limit]

    if not subject_ids:
        sys.exit("No subjects selected")

    scrapers = {
        "fps": FPSFullProfileScraper(),
        "npd": NPDFullProfileScraper(),
        "anywho": AnyWhoFullProfileScraper(),
        "zaba": ZabaHtmlScraper(timeout=args.timeout),
    }

    print(f"Full-profile scrape for {len(subject_ids)} subject(s): {', '.join(subject_ids)}\n")
    started = time.time()
    written = run(subject_ids, scrapers, notes=f"only={args.only} group={args.group} limit={args.limit}")
    print(f"\n✅ {written} rows in {time.time() - started:.0f}s -> testing.full_profile_results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
