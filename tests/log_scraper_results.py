#!/usr/bin/env python3
"""
Log scraper test results to Supabase.

Usage:
    from log_scraper_results import log_scrape_result

    log_scrape_result(
        scraper_type="anywho",
        scrape_mode="summary",
        input_data={"first_name": "John", "last_name": "Doe", "city": "SF", "state": "CA"},
        summary_results=[{"name": "John Doe", "age": "42", "phones": ["415-555-0123"]}],
        full_profile_results=[{...full data...}],
        status="success",
        execution_time_ms=245
    )
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Any

try:
    from supabase import create_client, Client
except ImportError:
    print("⚠️  supabase-py not installed. Run: pip install supabase")
    Client = None


class ScraperResultsLogger:
    """Log scraper test results to Supabase."""

    def __init__(self):
        """Initialize Supabase client."""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")

        if not self.url or not self.key:
            print("⚠️  SUPABASE_URL or SUPABASE_ANON_KEY not set")
            print("   Set these env vars or .env.local to log results")
            self.client = None
        else:
            self.client = create_client(self.url, self.key)

    def log_result(
        self,
        scraper_type: str,
        scrape_mode: str,
        input_data: Dict[str, Any],
        summary_results: Optional[List[Dict]] = None,
        full_profile_results: Optional[List[Dict]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        execution_time_ms: int = 0,
        notes: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Log a scraper test result to the database.

        Args:
            scraper_type: 'anywho', 'fps', 'zabasearch', or 'npd'
            scrape_mode: 'summary' or 'full_profile'
            input_data: Dict with first_name, last_name, city, state, phone
            summary_results: Results from summary page (list of person dicts)
            full_profile_results: Results from full profile page
            status: 'success', 'failed', or 'error'
            error_message: Error message if status != 'success'
            execution_time_ms: How long the scrape took
            notes: Optional tester notes

        Returns:
            Response from Supabase insert, or None if not connected
        """
        if not self.client:
            print("❌ Not connected to Supabase. Results not logged.")
            return None

        # Validate inputs
        valid_scrapers = {"anywho", "fps", "zabasearch", "npd"}
        if scraper_type not in valid_scrapers:
            raise ValueError(f"scraper_type must be one of {valid_scrapers}")

        valid_modes = {"summary", "full_profile"}
        if scrape_mode not in valid_modes:
            raise ValueError(f"scrape_mode must be one of {valid_modes}")

        valid_statuses = {"success", "failed", "error"}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")

        # Prepare record
        record = {
            "scraper_type": scraper_type,
            "scrape_mode": scrape_mode,
            "input_data": input_data,
            "summary_results": summary_results,
            "full_profile_results": full_profile_results,
            "status": status,
            "error_message": error_message,
            "execution_time_ms": execution_time_ms,
            "notes": notes,
        }

        try:
            response = (
                self.client.table("scraper_test_results")
                .insert(record)
                .execute()
            )
            print(f"✅ Logged {scraper_type} {scrape_mode} result (status: {status})")
            return response
        except Exception as e:
            print(f"❌ Failed to log result: {e}")
            return None

    def get_results(
        self,
        scraper_type: Optional[str] = None,
        scrape_mode: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> Optional[List[Dict]]:
        """
        Retrieve logged results from the database.

        Args:
            scraper_type: Filter by scraper ('anywho', 'fps', etc.)
            scrape_mode: Filter by mode ('summary', 'full_profile')
            status: Filter by status ('success', 'failed', 'error')
            limit: Max results to return

        Returns:
            List of result records
        """
        if not self.client:
            return None

        query = self.client.table("scraper_test_results")

        if scraper_type:
            query = query.eq("scraper_type", scraper_type)
        if scrape_mode:
            query = query.eq("scrape_mode", scrape_mode)
        if status:
            query = query.eq("status", status)

        try:
            response = (
                query.order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data
        except Exception as e:
            print(f"❌ Failed to retrieve results: {e}")
            return None


# Convenience function
def log_scrape_result(**kwargs) -> Optional[Dict]:
    """
    Quick function to log a scrape result.

    Usage:
        log_scrape_result(
            scraper_type="anywho",
            scrape_mode="summary",
            input_data={...},
            summary_results=[...],
            status="success",
            execution_time_ms=245
        )
    """
    logger = ScraperResultsLogger()
    return logger.log_result(**kwargs)


if __name__ == "__main__":
    # Example usage
    logger = ScraperResultsLogger()

    # Example result
    example_result = logger.log_result(
        scraper_type="anywho",
        scrape_mode="summary",
        input_data={
            "first_name": "John",
            "last_name": "Doe",
            "city": "San Francisco",
            "state": "CA",
        },
        summary_results=[
            {
                "name": "John Doe",
                "age": "42",
                "phones": ["415-555-0123"],
                "addresses": ["123 Main St, San Francisco, CA 94102"],
                "aliases": ["Johnny Doe"],
                "detail_link": "https://www.anywho.com/people/a12345",
            }
        ],
        status="success",
        execution_time_ms=245,
        notes="Test run - summary page scrape",
    )

    print("\nExample logged successfully!")
    print("\nTo query results:")
    print("  results = logger.get_results(scraper_type='anywho')")
