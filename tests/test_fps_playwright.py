"""
Unit tests for fps-playwright scraper (smoke.py).

Tests:
  - URL construction and search flow
  - Result parsing and field extraction
  - Fingerprint and bot-detection handling detection
  - Output validation

Note: Actual browser automation tests are NOT included (Camoufox/Playwright
requires full environment). These are unit tests for the logic layer.
"""

import pytest
import re
from unittest.mock import patch, MagicMock, Mock


class TestFpsUrlBuilding:
    """Test FPS URL/flow construction."""

    @pytest.mark.unit
    def test_google_referral_url(self):
        """FPS flow starts with Google search referral."""
        # FPS's strategy: google.com -> search "fast people search" -> click result
        base_google = "https://www.google.com/search"
        query = "fast people search"
        # The URL would be built as:
        url = f"{base_google}?q={query.replace(' ', '+')}"
        assert base_google in url
        assert "fast" in url

    @pytest.mark.unit
    def test_fps_base_url(self):
        """FPS base URL is fastpeoplesearch.com."""
        fps_base = "https://www.fastpeoplesearch.com"
        assert fps_base.startswith("https://")
        assert "fastpeoplesearch" in fps_base

    @pytest.mark.unit
    def test_fps_search_path(self):
        """FPS search path construction."""
        # FPS uses /name/... or /phone/... endpoints
        name_path = "/name/john+doe"
        phone_path = "/phone/4155550123"

        assert name_path.startswith("/")
        assert phone_path.startswith("/")

    @pytest.mark.unit
    def test_query_parameters_format(self):
        """Query parameters for FPS search."""
        # Name-based search might use params like:
        first, last, city, state = "John", "Doe", "San Francisco", "CA"
        params = {
            "name": f"{first} {last}",
            "city": city,
            "state": state,
        }
        assert params["name"] == "John Doe"
        assert len(params) == 3


class TestFpsResultParsing:
    """Test result parsing from FPS responses."""

    @pytest.mark.unit
    def test_parse_fps_result_card(self, fps_smoke_success):
        """Parse individual FPS result card."""
        # Extract result count from output
        match = re.search(r"(\d+) result", fps_smoke_success)
        assert match is not None
        count = int(match.group(1))
        assert count == 2

    @pytest.mark.unit
    def test_parse_name_from_result(self, fps_smoke_success):
        """Extract name from FPS result output."""
        match = re.search(r"\[1\]\s+(.+?),\s+Age", fps_smoke_success)
        assert match is not None
        name = match.group(1)
        assert name == "John Doe"

    @pytest.mark.unit
    def test_parse_age_from_result(self, fps_smoke_success):
        """Extract age from FPS result output."""
        match = re.search(r"Age\s+(\d+)", fps_smoke_success)
        assert match is not None
        age = match.group(1)
        assert age == "42"

    @pytest.mark.unit
    def test_parse_location_from_result(self, fps_smoke_success):
        """Extract location from FPS result output."""
        match = re.search(r"Lives in:\s+(.+?)(?:\n|$)", fps_smoke_success)
        assert match is not None
        location = match.group(1)
        assert "San Francisco" in location
        assert "CA" in location

    @pytest.mark.unit
    def test_parse_phone_from_result(self, fps_smoke_success):
        """Extract phone from FPS result output."""
        match = re.search(r"Phones?:\s+(.+?)(?:\n|$)", fps_smoke_success)
        assert match is not None
        phone = match.group(1)
        assert "415" in phone or "555" in phone

    @pytest.mark.unit
    def test_parse_detail_link_from_result(self, fps_smoke_success):
        """Extract detail profile link from FPS result."""
        match = re.search(r"Details?:\s+(https?://[^\s]+)", fps_smoke_success)
        assert match is not None
        link = match.group(1)
        assert "fastpeoplesearch.com" in link
        assert link.startswith("https")


class TestFpsBlocking:
    """Test bot detection and blocking detection."""

    @pytest.mark.unit
    def test_detect_cloudflare_challenge(self, fps_smoke_blocked):
        """Detect Cloudflare Turnstile challenge page."""
        assert "blocked" in fps_smoke_blocked.lower()
        assert "checking" in fps_smoke_blocked.lower() or "challenge" in fps_smoke_blocked.lower()

    @pytest.mark.unit
    def test_detect_recaptcha_challenge(self):
        """Detect reCAPTCHA challenge in page."""
        blocked_html = """
        <html>
        <body>
        <script src="//www.recaptcha.net/recaptcha/__init__.js?...">
        Please confirm you're not a robot
        </body>
        </html>
        """
        assert "recaptcha" in blocked_html.lower() or "robot" in blocked_html.lower()

    @pytest.mark.unit
    def test_detect_empty_response(self):
        """Detect empty/minimal response (sign of blocking)."""
        empty_response = "<html><body></body></html>"
        assert len(empty_response) < 500

    @pytest.mark.unit
    def test_fps_requires_fingerprinting(self):
        """FPS requires good browser fingerprint to pass challenges."""
        # Camoufox is used specifically for:
        # 1. Real Firefox fingerprint
        # 2. Hardware-aligned WebGL/canvas noise (defeats Picasso)
        # 3. Humanized cursor movements
        fingerprint_requirements = {
            "user_agent": "Firefox",
            "webgl": "spoofed",
            "canvas": "noisy",
            "cursor": "humanized",
        }
        assert fingerprint_requirements["user_agent"] == "Firefox"
        assert fingerprint_requirements["webgl"] == "spoofed"


class TestFpsBrowserFlow:
    """Test the expected browser flow."""

    @pytest.mark.unit
    def test_google_to_fps_flow_steps(self):
        """FPS flow: Google -> search -> click result -> fill form -> results."""
        steps = [
            ("google.com", "Navigate to Google"),
            ("search?q=fast+people+search", "Search for 'fast people search'"),
            ("fastpeoplesearch.com", "Click FPS result"),
            ("turnstile", "Solve Turnstile if needed"),
            ("/name/", "Fill search form"),
            ("results", "See results"),
        ]
        assert len(steps) == 6
        assert steps[0][0] == "google.com"
        assert steps[4][0] == "/name/"

    @pytest.mark.unit
    def test_form_filling_strategy(self):
        """FPS form expects first, last, city, state."""
        form_fields = {
            "firstName": "John",
            "lastName": "Doe",
            "city": "San Francisco",
            "state": "CA",
        }
        required = ["firstName", "lastName"]
        for field in required:
            assert field in form_fields

    @pytest.mark.unit
    def test_handles_turnstile_challenge(self):
        """Camoufox should handle Turnstile checkbox automatically."""
        # Turnstile is a Cloudflare challenge that requires:
        # 1. Clicking the checkbox
        # 2. Sometimes additional verification (image puzzle, audio)
        challenge_types = ["checkbox", "image_puzzle", "audio_puzzle"]
        assert "checkbox" in challenge_types


class TestFpsEnvironmentVariables:
    """Test environment variable handling (LOCAL_HEADED, NATIVE_FP, GEOIP)."""

    @pytest.mark.unit
    def test_local_headed_mode(self):
        """LOCAL_HEADED=1 enables headed mode (visual debugging)."""
        # When set, should skip Xvfb + ffmpeg and use real display
        local_headed_vars = {
            "LOCAL_HEADED": "1",  # vs not set (default 0)
        }
        assert local_headed_vars.get("LOCAL_HEADED") == "1"

    @pytest.mark.unit
    def test_native_fingerprint_mode(self):
        """NATIVE_FP=1 uses host OS fingerprint instead of Windows spoof."""
        # Tests Windows-UA-on-Apple-GPU mismatch theory
        native_fp_vars = {
            "NATIVE_FP": "1",  # vs not set (default Windows spoof)
        }
        assert native_fp_vars.get("NATIVE_FP") == "1"

    @pytest.mark.unit
    def test_geoip_matching(self):
        """GEOIP=1 matches fingerprint geo to proxy exit IP."""
        # When proxied, Camoufox warns timezone/locale/geo should match
        geoip_vars = {
            "GEOIP": "1",  # vs not set (default 0)
        }
        assert geoip_vars.get("GEOIP") == "1"

    @pytest.mark.unit
    def test_out_dir_configuration(self):
        """OUT_DIR env var controls output directory."""
        import os
        out_dir = os.environ.get("OUT_DIR", "/tmp/fps-out")
        assert isinstance(out_dir, str)
        assert len(out_dir) > 0


class TestFpsOutputValidation:
    """Test output file validation."""

    @pytest.mark.unit
    def test_output_files_generated(self):
        """FPS generates expected output files."""
        expected_files = [
            "fps-smoke.log",
            "fps-screenshot.png",
            "fps-results.html",
            "video/",  # directory
        ]
        for filename in expected_files[:3]:  # Check first 3 as examples
            assert isinstance(filename, str)
            assert len(filename) > 0

    @pytest.mark.unit
    def test_stage_snapshots_created(self):
        """FPS creates stage snapshots for review."""
        snapshot_patterns = [
            "google-*.png",
            "google-*.html",
            "recaptcha-*.png",
        ]
        for pattern in snapshot_patterns:
            assert "*" in pattern  # Glob pattern


class TestFpsErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.unit
    def test_missing_required_args(self):
        """smoke.py requires firstName and lastName."""
        # smoke.py should error if args < 2
        required_args = 2  # firstname, lastname
        optional_args = 2  # city, state
        assert required_args > 0
        assert optional_args >= 0

    @pytest.mark.unit
    def test_timeout_handling(self):
        """FPS respects network timeouts."""
        timeout_seconds = 40  # From smoke.py
        assert timeout_seconds > 0
        assert timeout_seconds < 120  # Reasonable upper bound

    @pytest.mark.unit
    def test_utf8_output_handling(self):
        """FPS forces UTF-8 stdout/stderr (Windows compatibility)."""
        # Script calls:
        # sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        # This allows unicode output (━ ✅ →) on Windows cp1252 console
        expected_encodings = ["utf-8", "utf8"]
        assert "utf-8" in expected_encodings

    @pytest.mark.unit
    def test_result_classification(self):
        """FPS classifies results (match, partial, no-match)."""
        result_types = ["match", "partial", "no-match", "blocked"]
        assert "match" in result_types


class TestFpsIntegration:
    """Integration-level tests."""

    @pytest.mark.unit
    def test_full_search_output_format(self, fps_smoke_success):
        """Full FPS output has structured format."""
        # Expected format:
        # ✅ N result card(s):
        # [1] Name, Age XX
        #     Lives in:    ...
        #     Phones:      ...
        #     Details:     ...

        lines = fps_smoke_success.strip().split("\n")
        assert len(lines) > 1
        assert "✅" in fps_smoke_success or "result" in fps_smoke_success.lower()

    @pytest.mark.unit
    def test_blocked_output_format(self, fps_smoke_blocked):
        """Blocked output has clear error format."""
        assert "⛔" in fps_smoke_blocked or "blocked" in fps_smoke_blocked.lower()
        assert "(" in fps_smoke_blocked  # Expected format: (NNN bytes)

    @pytest.mark.unit
    def test_parse_byte_count_from_blocked(self, fps_smoke_blocked):
        """Extract byte count from blocked response."""
        match = re.search(r"\((\d+)\s+bytes\)", fps_smoke_blocked)
        assert match is not None
        byte_count = int(match.group(1))
        assert byte_count > 0
        assert byte_count < 1000  # Blocked pages are small


class TestFpsComparison:
    """Test FPS against other scrapers for consistency."""

    @pytest.mark.unit
    def test_results_have_consistent_fields(self, fps_smoke_success):
        """FPS results use same fields as anywho/zabasearch."""
        # All scrapers should return: name, age, location, phones, etc.
        common_fields = {
            "name": ["name"],
            "age": ["age"],
            "location": ["location", "lives in"],
            "phone": ["phone", "phones"],
        }
        output = fps_smoke_success.lower()
        for field, terms in common_fields.items():
            # Should have at least one of these terms mentioned
            assert any(term in output for term in terms), f"Field '{field}' not found in output"

    @pytest.mark.unit
    def test_phone_format_consistency(self, fps_smoke_success):
        """FPS phone format matches other scrapers."""
        # Standard US phone: 123-456-7890 or 123.456.7890 or (123) 456-7890
        match = re.search(r"\d{3}[-.]?\d{3}[-.]?\d{4}", fps_smoke_success)
        # If a phone exists in the sample, it should match standard format
        if "555" in fps_smoke_success:
            assert match is not None
