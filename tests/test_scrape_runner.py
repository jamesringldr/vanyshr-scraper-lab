#!/usr/bin/env python3
"""
Unit Tests for Scrape Runner
=============================

Tests the scrape_runner CLI without making real HTTP calls (mocked).
Validates:
- Argument parsing
- Scrape ID generation
- Result transformation
- DB row normalization
- Error handling
"""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Import modules to test
import sys
from pathlib import Path

# Add tests dir to path
sys.path.insert(0, str(Path(__file__).parent))

from scrape_result_transformer import (
    transform_fps_result,
    transform_anywho_result,
    transform_zabasearch_result,
    normalize_db_row,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fps_result():
    """Sample FPS scraper result."""
    return {
        "name": "John Doe",
        "age": "42",
        "location": "San Francisco, CA",
        "phones": ["415-555-0123"],
        "detail_link": "https://www.fastpeoplesearch.com/name/john-doe",
    }


@pytest.fixture
def anywho_result():
    """Sample Anywho scraper result."""
    return {
        "name": "John Doe",
        "age": "42",
        "lives_in": "San Francisco, CA",
        "phones": ["415-555-0123"],
        "aka": "Johnny Doe",
        "related": "Jane Doe",
        "detail_link": "https://www.anywho.com/people/a12345",
    }


@pytest.fixture
def zabasearch_result():
    """Sample Zabasearch scraper result."""
    return {
        "name": "John Doe",
        "age": "42",
        "birth_year": "1982",
        "line_type": "Landline",
        "carrier": "AT&T",
        "location": "San Francisco, CA",
        "time_zone": "Pacific",
        "phones": ["415-555-0123"],
        "aliases": ["Johnny Doe", "J.D."],
        "most_recent_address": "123 Main St, San Francisco, CA 94102",
        "previous_addresses": ["456 Oak Ave, Oakland, CA 94601"],
        "email_domains": ["@example.com"],
        "previous_phones": ["415-555-0124"],
        "social_media": [],
        "jobs": [],
        "education": [],
        "professional_licenses": [],
        "related_persons": [{"name": "Jane Doe", "href": "/person/jane-doe"}],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Scrape ID Generation
# ─────────────────────────────────────────────────────────────────────────────

class TestScrapeIdGeneration:
    """Test scrape_id format generation."""

    def test_scrape_id_format(self):
        """Generate scrape_id with correct format."""
        from scrape_runner import generate_scrape_id

        # Use fixed timestamp for deterministic test
        ts = datetime(2026, 7, 29, 14, 22)
        scrape_id = generate_scrape_id("fps", ts)

        assert scrape_id == "fps.07.29.14.22"

    def test_scrape_id_anywho(self):
        """Generate scrape_id for anywho."""
        from scrape_runner import generate_scrape_id

        ts = datetime(2026, 7, 29, 11, 53)
        scrape_id = generate_scrape_id("anywho", ts)

        assert scrape_id == "anywho.07.29.11.53"

    def test_scrape_id_zabasearch(self):
        """Generate scrape_id for zabasearch."""
        from scrape_runner import generate_scrape_id

        ts = datetime(2026, 7, 29, 23, 59)
        scrape_id = generate_scrape_id("zabasearch", ts)

        assert scrape_id == "zabasearch.07.29.23.59"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Result Transformation
# ─────────────────────────────────────────────────────────────────────────────

class TestResultTransformation:
    """Test result transformation to DB schema."""

    def test_transform_fps_summary(self, fps_result):
        """Transform FPS result to summary format."""
        result = transform_fps_result(fps_result, "summary")

        assert result["summary_results"] is not None
        assert result["summary_results"]["name"] == "John Doe"
        assert result["summary_results"]["age"] == "42"
        assert "415-555-0123" in result["summary_results"]["phones"]

    def test_transform_fps_full(self, fps_result):
        """Transform FPS result to full format."""
        result = transform_fps_result(fps_result, "full")

        assert result["summary_results"] is None
        assert result["full_profile_results"] is not None
        assert result["full_profile_results"]["name"] == "John Doe"

    def test_transform_fps_both(self, fps_result):
        """Transform FPS result to both formats."""
        result = transform_fps_result(fps_result, "both")

        assert result["summary_results"] is not None
        assert result["full_profile_results"] is not None

    def test_transform_anywho_summary(self, anywho_result):
        """Transform Anywho result to summary format."""
        result = transform_anywho_result(anywho_result, "summary")

        assert result["summary_results"] is not None
        assert result["summary_results"]["name"] == "John Doe"
        assert result["summary_results"]["aka"] == "Johnny Doe"
        assert result["summary_results"]["related"] == "Jane Doe"

    def test_transform_zabasearch_full(self, zabasearch_result):
        """Transform Zabasearch result to full format."""
        result = transform_zabasearch_result(zabasearch_result, "full")

        assert result["full_profile_results"] is not None
        assert result["full_profile_results"]["carrier"] == "AT&T"
        assert result["full_profile_results"]["birth_year"] == "1982"
        assert result["full_profile_results"]["line_type"] == "Landline"
        assert "Pacific" == result["full_profile_results"]["time_zone"]

    def test_transform_zabasearch_summary(self, zabasearch_result):
        """Transform Zabasearch result to summary format."""
        result = transform_zabasearch_result(zabasearch_result, "summary")

        assert result["summary_results"] is not None
        assert result["summary_results"]["name"] == "John Doe"
        assert result["summary_results"]["age"] == "42"
        assert "415-555-0123" in result["summary_results"]["phones"]


# ─────────────────────────────────────────────────────────────────────────────
# Tests: DB Row Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestDbRowNormalization:
    """Test creation of normalized DB rows."""

    def test_normalize_db_row_fps(self, fps_result):
        """Normalize FPS result to DB row."""
        row = normalize_db_row(
            scrape_id="fps.07.29.14.22",
            target="fps",
            mode="local",
            scrape_type="summary",
            input_data={"first_name": "John", "last_name": "Doe"},
            result=fps_result,
            status="success",
            response_time_ms=2345,
            response_bytes=4250,
        )

        assert row["scrape_id"] == "fps.07.29.14.22"
        assert row["target"] == "fps"
        assert row["mode"] == "local"
        assert row["scrape_type"] == "summary"
        assert row["status"] == "success"
        assert row["response_time_ms"] == 2345
        assert row["response_bytes"] == 4250
        assert row["summary_results"] is not None
        assert row["summary_results"]["name"] == "John Doe"

    def test_normalize_db_row_with_errors(self, fps_result):
        """Normalize DB row with errors."""
        row = normalize_db_row(
            scrape_id="fps.07.29.14.22",
            target="fps",
            mode="local",
            scrape_type="summary",
            input_data={},
            result=fps_result,
            status="failed",
            response_time_ms=0,
            response_bytes=0,
            errors="Worker crashed",
        )

        assert row["status"] == "failed"
        assert row["errors"] == "Worker crashed"

    def test_normalize_db_row_blocked(self, fps_result):
        """Normalize DB row with blocked status."""
        row = normalize_db_row(
            scrape_id="fps.07.29.14.22",
            target="fps",
            mode="prod",
            scrape_type="summary",
            input_data={},
            result=fps_result,
            status="blocked",
            response_time_ms=5000,
            response_bytes=402,
            errors="Cloudflare Turnstile challenge",
        )

        assert row["status"] == "blocked"
        assert row["response_bytes"] == 402


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Argument Parsing
# ─────────────────────────────────────────────────────────────────────────────

class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_input_single_value(self):
        """Parse single key=value input."""
        from scrape_runner import parse_input

        result = parse_input(["first_name=John"])
        assert result == {"first_name": "John"}

    def test_parse_input_multiple_values(self):
        """Parse multiple key=value inputs."""
        from scrape_runner import parse_input

        result = parse_input([
            "first_name=John",
            "last_name=Doe",
            "city=San Francisco",
            "state=CA",
        ])

        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["city"] == "San Francisco"
        assert result["state"] == "CA"

    def test_parse_input_quoted_values(self):
        """Parse input with quoted values."""
        from scrape_runner import parse_input

        result = parse_input([
            'first_name="John"',
            "last_name='Doe'",
        ])

        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"

    def test_parse_input_invalid_format(self):
        """Fail on invalid input format."""
        from scrape_runner import parse_input

        with pytest.raises(ValueError):
            parse_input(["invalid_format"])


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Schema Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaValidation:
    """Validate DB row matches schema."""

    def test_db_row_has_all_required_fields(self, fps_result):
        """DB row contains all required fields."""
        row = normalize_db_row(
            scrape_id="fps.07.29.14.22",
            target="fps",
            mode="local",
            scrape_type="summary",
            input_data={},
            result=fps_result,
            status="success",
            response_time_ms=1000,
            response_bytes=1000,
        )

        required_fields = [
            "scrape_id", "target", "mode", "scrape_type",
            "input_data", "summary_results", "full_profile_results",
            "errors", "status", "response_time_ms", "response_bytes",
        ]

        for field in required_fields:
            assert field in row, f"Missing field: {field}"

    def test_db_row_types(self, fps_result):
        """DB row fields have correct types."""
        row = normalize_db_row(
            scrape_id="fps.07.29.14.22",
            target="fps",
            mode="local",
            scrape_type="summary",
            input_data={"test": "value"},
            result=fps_result,
            status="success",
            response_time_ms=1234,
            response_bytes=5000,
        )

        assert isinstance(row["scrape_id"], str)
        assert isinstance(row["target"], str)
        assert isinstance(row["mode"], str)
        assert isinstance(row["scrape_type"], str)
        assert isinstance(row["input_data"], dict)
        assert isinstance(row["response_time_ms"], int)
        assert isinstance(row["response_bytes"], int)
        assert row["status"] in ["success", "partial", "failed", "timeout", "blocked"]


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests (Mock HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class TestScraperRunnerIntegration:
    """Test ScraperRunner with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_fps_runner_success(self, fps_result):
        """Test FPS runner success case."""
        from scrape_runner import ScraperRunner

        runner = ScraperRunner(
            target="fps",
            mode="local",
            scrape_type="summary",
            input_data={"first_name": "John", "last_name": "Doe"},
        )

        # Mock the run method
        with patch.object(runner, "run_fps", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "scrape_id": runner.scrape_id,
                "target": "fps",
                "mode": "local",
                "scrape_type": "summary",
                "input_data": runner.input_data,
                "results": [fps_result],
                "status": "success",
                "response_time_ms": 2345,
                "response_bytes": 4250,
                "errors": None,
            }

            result = await runner.run()

            assert result["status"] == "success"
            assert len(result["results"]) == 1
            assert result["results"][0]["name"] == "John Doe"


# ─────────────────────────────────────────────────────────────────────────────
# Run Tests
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
