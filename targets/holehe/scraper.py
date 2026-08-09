# targets/holehe/scraper.py
"""
Holehe Email Scraper

Pluggable scraper module for vanyshr-mono app.
Checks if an email has been exposed across multiple online services.

Standard interface: scraper.run(params) -> Output
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import subprocess
import json

from .parser import HoleheParser
from .models import ScrapeOutput, ServiceResult

logger = logging.getLogger(__name__)


@dataclass
class ScraperParams:
    """Input parameters for Holehe scraper"""
    email: str
    onlyUsed: bool = False
    noColor: bool = True  # Default to no color for parsing
    noClear: bool = True  # Default to no clear for capturing output
    noPasswordRecovery: bool = False
    csv: bool = False
    timeout: int = 10


class HoleheScraper:
    """Holehe email scraper implementation"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.parser = HoleheParser()

    async def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """
        Main entry point for email reconnaissance with Holehe.

        Args:
            params: Dictionary with keys: email, [onlyUsed, timeout, ...]

        Returns:
            ScrapeOutput with service check results
        """
        try:
            # Validate and normalize params
            scraper_params = ScraperParams(**params)

            logger.info(f"Holehe Scrape started: {scraper_params.email}")

            start_time = datetime.utcnow()

            # Run Holehe
            results = await self._run_holehe(scraper_params)

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Summarize results
            summary = self._summarize_results(results)

            output = ScrapeOutput(
                source="holehe",
                search_params=asdict(scraper_params),
                results=results,
                summary=summary,
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=execution_time_ms,
                status="success" if results else "failed"
            )

            logger.info(f"Holehe Scrape completed: {summary['servicesFound']} found, "
                       f"{execution_time_ms}ms")

            return output

        except Exception as e:
            logger.error(f"Holehe Scrape failed: {str(e)}", exc_info=True)
            return ScrapeOutput(
                source="holehe",
                search_params=params,
                results=[],
                summary={},
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=0,
                status="failed",
                error=str(e)
            )

    async def _run_holehe(self, params: ScraperParams) -> List[Dict[str, Any]]:
        """Run Holehe command and parse output"""
        try:
            import shutil

            # Find holehe in PATH or use full path
            holehe_bin = shutil.which('holehe')
            if not holehe_bin:
                # Try to find it in common locations
                import os
                possible_paths = [
                    '/Users/jameso/DevWork/vanyshr-stack/vanyshr-scraper-lab/holehe-email-scrape/venv/bin/holehe',
                    os.path.expanduser('~/.venv/bin/holehe'),
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        holehe_bin = path
                        break

            if not holehe_bin:
                raise Exception("holehe binary not found in PATH or common locations")

            # Build holehe CLI arguments
            args = [holehe_bin, params.email]

            if params.onlyUsed:
                args.append('--only-used')
            if params.noColor:
                args.append('--no-color')
            if params.noClear:
                args.append('--no-clear')
            if params.noPasswordRecovery:
                args.append('-NP')
            if params.csv:
                args.append('-C')

            args.extend(['-T', str(params.timeout)])

            logger.debug(f"Running: {' '.join(args)}")

            # Run holehe subprocess
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_subprocess,
                args
            )

            if result['returncode'] != 0 and result['returncode'] != 1:
                raise Exception(f"Holehe failed: {result['stderr']}")

            # Parse the output
            cli_output = result['stdout']
            results = self.parser.parse_cli_output(cli_output)

            return results

        except Exception as e:
            logger.error(f"Error running holehe: {str(e)}")
            return []

    @staticmethod
    def _run_subprocess(args: List[str]) -> Dict[str, Any]:
        """Run subprocess and capture output"""
        import subprocess
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=120  # Overall timeout
            )
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                'returncode': 124,
                'stdout': '',
                'stderr': 'Command timed out',
            }

    def _summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """Summarize result statistics using parser"""
        return self.parser.get_summary_stats(results)


# Standard interface for vanyshr-mono integration
async def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard entry point for vanyshr-mono scraper sequences.

    This function is imported and called by:
    - QuickScan workflow (email reconnaissance only)
    - Subscriber monitoring workflow (continuous monitoring)

    Args:
        params: {email, timeout, onlyUsed, ...}

    Returns:
        Dictionary matching ScrapeOutput schema (JSON-serializable)
    """
    scraper = HoleheScraper(timeout=params.get("timeout", 10))
    output = await scraper.run(params)
    return asdict(output)

