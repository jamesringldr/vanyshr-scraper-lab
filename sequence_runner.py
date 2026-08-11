"""
Sequence Runner - Main orchestrator for quickscan flow.
Handles two-phase scanning: Summary search with deduplication, then full profile enrichment.

PHASE 1: Parallel summary scraping & deduplication
  - Scrape summaries from 4 brokers in parallel (FPS, NPD, AnyWho, Zaba)
  - Deduplicate using weighted scoring algorithm
  - Return ranked list of potential matches for user selection

PHASE 2: Full profiles & enrichment (after user selects)
  - Scrape full profiles from all 4 brokers in parallel
  - Extract emails and consolidate across brokers
  - Enrich with Holehe (online services) and Leakcheck (data breaches)
  - Consolidate into unified profile with deduplication
"""

import asyncio
import logging
import sys
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Load .env.local if it exists
load_dotenv('.env.local')

# Add sequence worktree for HTML scrapers
sys.path.insert(0, str(Path(__file__).parent))

from data_models import (
    QuickScanInput, ScrapeResult, BrokerName, SequenceOutput
)
from dedup_engine import DedupEngine

# Import HTML-based scrapers (cost-efficient primary method)
from fps_html_scraper import FPSHtmlScraper
from npd_html_scraper import NPDHtmlScraper
from anywho_html_scraper import AnyWhoHtmlScraper

# Zaba: residential IP service on serv01 (not HTML, IP gets blocked)
from zaba_residential_scraper import ZabaResidentialScraper

# Phase 2: Full Profiles & Enrichment
from fps_full_profile_scraper import FPSFullProfileScraper
from npd_full_profile_scraper import NPDFullProfileScraper
from anywho_full_profile_scraper import AnyWhoFullProfileScraper
from zaba_full_profile_scraper import ZabaFullProfileScraper
from email_extractor import EmailExtractor
from holehe_enricher import HoleheEnricher
from leakcheck_enricher import LeakcheckEnricher
from profile_consolidator import ProfileConsolidator

logger = logging.getLogger(__name__)


class SequenceRunner:
    """Main orchestrator for quickscan sequence using HTML scrapers"""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60, use_zaba_residential: bool = True):
        """
        Initialize sequence runner with HTML-based scrapers.

        Args:
            api_key: context.dev API key (uses env var if not provided)
            timeout: Timeout for each scraper (seconds)
            use_zaba_residential: Use serv01:8788 residential service for Zaba (true)
                                  or HTML method (false, will fail with IP blocking)
        """
        self.api_key = api_key or os.environ.get('CONTEXT_DEV_API_KEY')
        self.timeout = timeout
        self.use_zaba_residential = use_zaba_residential
        self.dedup_engine = DedupEngine()

        # Phase 2 components
        self.email_extractor = EmailExtractor()
        self.holehe_enricher = HoleheEnricher(timeout=timeout)
        self.leakcheck_enricher = LeakcheckEnricher(timeout=timeout)
        self.profile_consolidator = ProfileConsolidator()

        # Phase 2 scrapers
        self.full_profile_scrapers = {
            BrokerName.FPS: FPSFullProfileScraper(api_key=self.api_key),
            BrokerName.NPD: NPDFullProfileScraper(api_key=self.api_key),
            BrokerName.ANYWHO: AnyWhoFullProfileScraper(api_key=self.api_key),
            BrokerName.ZABA: ZabaFullProfileScraper(),
        }

        # Initialize scrapers
        self.scrapers = {
            BrokerName.FPS: FPSHtmlScraper(api_key=self.api_key, timeout=timeout),
            BrokerName.NPD: NPDHtmlScraper(api_key=self.api_key, timeout=timeout),
            BrokerName.ANYWHO: AnyWhoHtmlScraper(api_key=self.api_key, timeout=timeout),
            # Zaba: use residential IP service (serv01:8788) - HTML method gets IP-blocked
            BrokerName.ZABA: ZabaResidentialScraper(timeout=timeout, use_prod=use_zaba_residential),
        }

        logger.info(
            f"SequenceRunner initialized: "
            f"Phase 1 (Summary: FPS/NPD/AnyWho HTML + Zaba residential), "
            f"Phase 2 (Full profiles + Enrichment ready)"
        )

    async def quickscan(self, user_input: QuickScanInput) -> SequenceOutput:
        """
        Run quickscan sequence: Parallel summaries → Deduplication.

        Args:
            user_input: User's search input (first_name, last_name, city, state)

        Returns:
            SequenceOutput with deduplicated profiles
        """
        start_time = time.time()

        logger.info(
            f"QuickScan started: {user_input.first_name} {user_input.last_name}, "
            f"{user_input.city}, {user_input.state}"
        )

        # PHASE 1: Parallel Summary Scraping
        scrape_results = await self._scrape_summaries_parallel(user_input)

        # PHASE 2: Deduplication & Scoring
        dedup_groups = self.dedup_engine.deduplicate(scrape_results)

        # Build output
        total_time_ms = int((time.time() - start_time) * 1000)

        output = SequenceOutput(
            dedup_groups=dedup_groups,
            raw_results=scrape_results,
            metadata={
                'total_time_ms': total_time_ms,
                'phase': 'summary',
                'phase_timings': {
                    'scrape': sum(r.timing_ms for r in scrape_results.values()),
                    'dedup': total_time_ms - sum(r.timing_ms for r in scrape_results.values()),
                },
                'profiles_found': len(dedup_groups),
                'brokers_scraped': list(scrape_results.keys()),
            }
        )

        logger.info(
            f"QuickScan complete: {len(dedup_groups)} deduplicated profiles, "
            f"{total_time_ms}ms total"
        )

        return output

    async def _scrape_summaries_parallel(
        self,
        user_input: QuickScanInput
    ) -> Dict[str, ScrapeResult]:
        """
        Scrape summaries from all 4 brokers in parallel.

        Args:
            user_input: Search parameters

        Returns:
            Dict of broker name -> ScrapeResult
        """
        logger.info("Starting parallel summary scraping...")

        # Create tasks for all brokers
        tasks = {
            BrokerName.FPS: self._scrape_broker(
                BrokerName.FPS,
                self.scrapers[BrokerName.FPS],
                user_input
            ),
            BrokerName.NPD: self._scrape_broker(
                BrokerName.NPD,
                self.scrapers[BrokerName.NPD],
                user_input
            ),
            BrokerName.ANYWHO: self._scrape_broker(
                BrokerName.ANYWHO,
                self.scrapers[BrokerName.ANYWHO],
                user_input
            ),
            BrokerName.ZABA: self._scrape_broker(
                BrokerName.ZABA,
                self.scrapers[BrokerName.ZABA],
                user_input
            ),
        }

        # Run all in parallel
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Process results
        scrape_results = {}
        for broker, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"{broker} scrape failed: {result}")
                scrape_results[broker.value] = ScrapeResult(
                    broker=broker,
                    status="failed",
                    error=str(result)
                )
            else:
                scrape_results[broker.value] = result

        logger.info(
            f"Parallel scraping complete: "
            f"{sum(1 for r in scrape_results.values() if r.status == 'success')} "
            f"successful out of 4"
        )

        return scrape_results

    async def _scrape_broker(
        self,
        broker: BrokerName,
        scraper,
        user_input: QuickScanInput
    ) -> ScrapeResult:
        """
        Scrape a single broker (runs in parallel).

        Args:
            broker: Broker name
            scraper: Scraper instance
            user_input: Search parameters

        Returns:
            ScrapeResult
        """
        start_time = time.time()

        try:
            logger.debug(f"Scraping {broker}...")

            # Run scraper (synchronous, wrap in executor if needed)
            output = scraper.run({
                'firstName': user_input.first_name,
                'lastName': user_input.last_name,
                'city': user_input.city,
                'state': user_input.state,
                'timeout': self.timeout,
            })

            timing_ms = int((time.time() - start_time) * 1000)

            # Convert ScrapeOutput to ScrapeResult
            summary_results = []
            if output.summary_results:
                for summary in output.summary_results:
                    # Parse age if present
                    age = None
                    if hasattr(summary, 'age') and summary.age:
                        try:
                            age = int(summary.age) if isinstance(summary.age, (int, str)) else None
                        except (ValueError, TypeError):
                            age = None

                    from data_models import SummaryResult as SR
                    sr = SR(
                        broker=broker,
                        full_name=summary.fullName,
                        address=getattr(summary, 'address', getattr(summary, 'addressPreview', '')),
                        age_range=str(summary.age) if hasattr(summary, 'age') and summary.age else "",
                        age=age,
                        location=getattr(summary, 'location', ''),
                        profile_url=getattr(summary, 'profileUrl', ''),
                    )
                    summary_results.append(sr)

            logger.debug(
                f"{broker} scraped: {len(summary_results)} summaries, "
                f"{timing_ms}ms"
            )

            return ScrapeResult(
                broker=broker,
                summaries=summary_results,
                status=output.status if hasattr(output, 'status') else 'success',
                error=getattr(output, 'error', None),
                timing_ms=timing_ms,
            )

        except Exception as e:
            timing_ms = int((time.time() - start_time) * 1000)
            logger.error(f"{broker} scrape failed: {e}", exc_info=True)

            return ScrapeResult(
                broker=broker,
                status="failed",
                error=str(e),
                timing_ms=timing_ms,
            )

    async def full_profile_phase(
        self, dedup_group, user_input: QuickScanInput
    ):
        """
        Phase 2: Scrape full profiles, extract enrichment data, consolidate.

        Args:
            dedup_group: Selected DedupGroup from Phase 1
            user_input: Original search input (for full profile scraping)

        Returns:
            ConsolidatedProfile with full data and enrichment
        """
        start_time = time.time()
        logger.info(f"Phase 2: Scraping full profiles for {dedup_group.primary_name}")

        # Step 1: Scrape full profiles from all brokers in parallel
        logger.info("Step 1: Scraping full profiles...")
        full_profiles = {}

        # Get profile links from dedup group members
        profile_links = {
            member.summary.broker.value: member.summary.profile_url
            for member in dedup_group.members
            if member.summary.profile_url
        }

        for broker_name, scraper in self.full_profile_scrapers.items():
            profile_url = profile_links.get(broker_name.value)
            if not profile_url:
                logger.debug(f"No profile URL for {broker_name.value}")
                continue

            try:
                if broker_name == BrokerName.ZABA:
                    # Zaba doesn't have profile URLs, it returns full data directly
                    # For now, skip full profile scraping for Zaba
                    continue
                else:
                    profile = scraper.scrape_profile(profile_url)
                    if profile:
                        full_profiles[broker_name.value] = profile

            except Exception as e:
                logger.error(f"Error scraping {broker_name} profile: {e}")

        if not full_profiles:
            logger.warning("No full profiles found")
            return None

        # Step 2: Extract emails
        logger.info("Step 2: Extracting emails...")
        emails = self.email_extractor.extract_from_profiles(full_profiles)
        logger.info(f"Found {len(emails)} unique emails")

        # Step 3: Enrich with Holehe and Leakcheck
        logger.info("Step 3: Enriching with services and breach data...")
        enrichment_data = {
            "services_found": [],
            "breaches": [],
        }

        if emails:
            # Get first email for enrichment (could do all, but that's slower)
            primary_email = sorted(emails)[0]

            # Holehe enrichment
            holehe_result = self.holehe_enricher.enrich_email(primary_email)
            if holehe_result and holehe_result.get("status") == "success":
                enrichment_data["services_found"] = holehe_result.get(
                    "services_found", []
                )

            # Leakcheck enrichment
            leakcheck_result = self.leakcheck_enricher.enrich_email(primary_email)
            if leakcheck_result and leakcheck_result.get("status") == "success":
                enrichment_data["breaches"] = leakcheck_result.get("breaches", [])

        # Step 4: Consolidate profiles
        logger.info("Step 4: Consolidating profiles...")
        consolidated = self.profile_consolidator.consolidate(
            profiles=full_profiles,
            person_id=dedup_group.dedup_id,
            confidence=dedup_group.average_confidence,
            enrichment_data=enrichment_data,
        )

        phase2_time_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Phase 2 complete in {phase2_time_ms}ms")

        return consolidated


async def main():
    """Test quickscan with real data"""
    import os

    api_key = os.environ.get('CONTEXT_DEV_API_KEY')
    if not api_key:
        print("❌ CONTEXT_DEV_API_KEY not set")
        return

    # Initialize runner
    runner = SequenceRunner(api_key=api_key)

    # Test input
    user_input = QuickScanInput(
        first_name="James",
        last_name="Oehring",
        city="Cameron",
        state="MO"
    )

    print("\n" + "=" * 80)
    print("QUICKSCAN TEST")
    print("=" * 80)

    # Run quickscan
    output = await runner.quickscan(user_input)

    # Display results
    print(f"\n✅ Quickscan Complete!")
    print(f"   Total Time: {output.metadata['total_time_ms']}ms")
    print(f"   Profiles Found: {len(output.dedup_groups)}")
    print()

    for i, group in enumerate(output.dedup_groups, 1):
        display = group.to_display()
        print(f"Profile {i}:")
        print(f"  Name: {display['name']}")
        print(f"  Age: {display['age']}")
        print(f"  Location: {display['city']}, {display['state']}")
        print(f"  Sources: {', '.join(display['sources'])}")
        print(f"  Confidence: {display['confidence']}%")
        if display.get('age_note'):
            print(f"  Note: {display['age_note']}")
        print()

    # Show raw timing
    print("Broker Timings:")
    for broker, result in output.raw_results.items():
        print(f"  {broker}: {result.timing_ms}ms ({result.status})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
