"""
Scraper Sequence Runner

Orchestrates multiple scraper modules (FPS, NPD, AnyWho) to gather data from
all sources for a single person search. Runs scrapers in parallel where possible,
aggregates results, and handles failures gracefully.

Usage:
    from scraper_sequence import SequenceRunner

    runner = SequenceRunner()
    results = runner.run({
        'firstName': 'James',
        'lastName': 'Oehring',
        'city': 'Cameron',
        'state': 'MO'
    })

    # Results contains:
    # - fps: FPS scraper results
    # - npd: NPD scraper results
    # - anywho: AnyWho scraper results
    # - aggregate: merged data across all sources
    # - timing: execution time per scraper
"""

import sys
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

# targets/ models live alongside this module
sys.path.insert(0, str(Path(__file__).parent))

from targets.fps.scraper import FPSScraper as FPSScraperClass
from targets.npd.scraper import NPDScraper as NPDScraperClass
from targets.anywho.scraper import AnyWhoScraper as AnyWhoScraperClass

logger = logging.getLogger(__name__)


@dataclass
class ScraperResult:
    """Result from a single scraper"""
    scraper_name: str
    status: str  # 'success', 'no_results', 'failed', 'skipped'
    execution_time_ms: int
    summary_count: int = 0
    profile_found: bool = False
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@dataclass
class AggregatedProfile:
    """Aggregated profile from multiple scrapers"""
    name: str = ""
    age: Optional[int] = None
    address: str = ""
    phones: List[str] = None
    emails: List[str] = None
    relatives: List[str] = None
    sources: List[str] = None  # Which scrapers found this

    def __post_init__(self):
        if self.phones is None:
            self.phones = []
        if self.emails is None:
            self.emails = []
        if self.relatives is None:
            self.relatives = []
        if self.sources is None:
            self.sources = []


@dataclass
class SequenceOutput:
    """Output from sequence runner"""
    query_params: Dict[str, Any]
    timestamp: str
    total_time_ms: int

    # Individual scraper results
    fps_result: Optional[ScraperResult] = None
    npd_result: Optional[ScraperResult] = None
    anywho_result: Optional[ScraperResult] = None

    # Aggregated data
    aggregate: Optional[AggregatedProfile] = None

    # Summary stats
    scrapers_attempted: int = 0
    scrapers_successful: int = 0
    scrapers_failed: int = 0


class SequenceRunner:
    """Orchestrates multiple scrapers to gather comprehensive person data"""

    SCRAPERS = [
        ("fps", FPSScraperClass, "FastPeopleSearch"),
        ("npd", NPDScraperClass, "National Public Data"),
        ("anywho", AnyWhoScraperClass, "AnyWho"),
    ]

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        """
        Initialize sequence runner.

        Args:
            timeout: Timeout for each scraper in seconds
            api_key: Optional API key for context.dev (uses env var if not provided)
        """
        self.timeout = timeout
        self.api_key = api_key
        self.results: Dict[str, ScraperResult] = {}

    def _run_single_scraper(self, scraper_class, scraper_name: str, params: Dict[str, Any]) -> ScraperResult:
        """
        Run a single scraper and return result.

        Args:
            scraper_class: The scraper class to instantiate
            scraper_name: Name of the scraper (for logging)
            params: Search parameters

        Returns:
            ScraperResult with status and data
        """
        start_time = datetime.utcnow()

        try:
            logger.info(f"Starting {scraper_name}...")

            # Instantiate and run scraper
            scraper = scraper_class(timeout=self.timeout, api_key=self.api_key)
            output = scraper.run(params)

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Check if we got results
            summary_count = len(output.summary_results) if hasattr(output, 'summary_results') else 0
            profile_found = output.profile is not None if hasattr(output, 'profile') else False

            logger.info(f"{scraper_name} completed: status={output.status}, time={execution_time_ms}ms")

            return ScraperResult(
                scraper_name=scraper_name,
                status=output.status,
                execution_time_ms=execution_time_ms,
                summary_count=summary_count,
                profile_found=profile_found,
                data=asdict(output) if hasattr(output, '__dataclass_fields__') else output
            )

        except Exception as e:
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_msg = str(e)[:200]
            logger.error(f"{scraper_name} failed: {error_msg}")

            return ScraperResult(
                scraper_name=scraper_name,
                status="failed",
                execution_time_ms=execution_time_ms,
                error=error_msg
            )

    def _aggregate_results(self, results: Dict[str, ScraperResult]) -> AggregatedProfile:
        """
        Aggregate results from multiple scrapers.

        Args:
            results: Dictionary of scraper results

        Returns:
            Aggregated profile combining data from all sources
        """
        aggregate = AggregatedProfile()

        for scraper_key, result in results.items():
            if result.status not in ("success", "no_results") or not result.data:
                continue

            data = result.data
            scraper_name = result.scraper_name

            # Extract profile data (handle different structures)
            profile = None
            if "profile" in data and data["profile"]:
                profile = data["profile"]
            elif "profiles" in data and data["profiles"]:
                profile = data["profiles"][0]  # First profile if multiple

            if not profile:
                continue

            aggregate.sources.append(scraper_name)

            # Merge name (prefer first found)
            if not aggregate.name and profile.get("fullName"):
                aggregate.name = profile["fullName"]

            # Merge age (take first found)
            if aggregate.age is None and profile.get("age"):
                aggregate.age = profile["age"]

            # Merge address
            if not aggregate.address:
                current_addr = profile.get("currentAddress", {})
                if isinstance(current_addr, dict):
                    aggregate.address = current_addr.get("formatted", "")
                elif isinstance(current_addr, str):
                    aggregate.address = current_addr

            # Merge phones (deduplicate)
            if profile.get("phoneNumbers"):
                for phone_obj in profile["phoneNumbers"]:
                    if isinstance(phone_obj, dict):
                        phone_num = phone_obj.get("number", "")
                    else:
                        phone_num = str(phone_obj)
                    if phone_num and phone_num not in aggregate.phones:
                        aggregate.phones.append(phone_num)

            # Merge emails (deduplicate)
            if profile.get("emailAddresses"):
                for email in profile["emailAddresses"]:
                    if email and email not in aggregate.emails:
                        aggregate.emails.append(email)

            # Merge relatives (deduplicate)
            if profile.get("relatives"):
                for rel_obj in profile["relatives"]:
                    if isinstance(rel_obj, dict):
                        rel_name = rel_obj.get("name", "")
                    else:
                        rel_name = str(rel_obj)
                    if rel_name and rel_name not in aggregate.relatives:
                        aggregate.relatives.append(rel_name)

        return aggregate

    def run(self, params: Dict[str, Any]) -> SequenceOutput:
        """
        Run the complete scraper sequence.

        Args:
            params: Search parameters (firstName, lastName, city, state, timeout)

        Returns:
            SequenceOutput with all results and aggregated data
        """
        start_time = datetime.utcnow()

        logger.info(f"Sequence started: {params}")

        output = SequenceOutput(
            query_params=params,
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_time_ms=0,
            scrapers_attempted=0,
            scrapers_successful=0,
            scrapers_failed=0
        )

        # Run each scraper
        results = {}
        for scraper_key, scraper_class, scraper_name in self.SCRAPERS:
            output.scrapers_attempted += 1
            result = self._run_single_scraper(scraper_class, scraper_name, params)
            results[scraper_key] = result

            if result.status in ("success", "no_results"):
                output.scrapers_successful += 1
            else:
                output.scrapers_failed += 1

        # Store individual results
        output.fps_result = results.get("fps")
        output.npd_result = results.get("npd")
        output.anywho_result = results.get("anywho")

        # Aggregate results
        output.aggregate = self._aggregate_results(results)

        # Calculate total time
        output.total_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(f"Sequence completed: {output.scrapers_successful}/{output.scrapers_attempted} successful, "
                   f"total time: {output.total_time_ms}ms")

        return output

    def print_results(self, output: SequenceOutput) -> None:
        """Pretty-print sequence results."""
        print("\n" + "=" * 80)
        print("SCRAPER SEQUENCE RESULTS")
        print("=" * 80)

        print(f"\nQuery: {output.query_params['firstName']} {output.query_params['lastName']}, "
              f"{output.query_params['city']}, {output.query_params['state']}")
        print(f"Total Time: {output.total_time_ms}ms")
        print(f"Scrapers: {output.scrapers_successful}/{output.scrapers_attempted} successful\n")

        # Individual results
        print("INDIVIDUAL RESULTS")
        print("-" * 80)
        for result in [output.fps_result, output.npd_result, output.anywho_result]:
            if not result:
                continue
            print(f"{result.scraper_name}:")
            print(f"  Status: {result.status}")
            print(f"  Time: {result.execution_time_ms}ms")
            print(f"  Summaries: {result.summary_count}")
            print(f"  Profile: {'Yes' if result.profile_found else 'No'}")
            if result.error:
                print(f"  Error: {result.error}")

        # Aggregated results
        print("\nAGGREGATED RESULTS")
        print("-" * 80)
        agg = output.aggregate
        print(f"Name: {agg.name}")
        print(f"Age: {agg.age}")
        print(f"Address: {agg.address}")
        print(f"Phones: {len(agg.phones)} found - {', '.join(agg.phones[:2])}")
        print(f"Emails: {len(agg.emails)} found - {', '.join(agg.emails[:2])}")
        print(f"Relatives: {len(agg.relatives)} found")
        print(f"Sources: {', '.join(agg.sources)}")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    runner = SequenceRunner(timeout=60)

    result = runner.run({
        "firstName": "James",
        "lastName": "Oehring",
        "city": "Cameron",
        "state": "MO"
    })

    runner.print_results(result)
