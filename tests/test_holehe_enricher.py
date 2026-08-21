"""
Data-quality tests for holehe_enricher against recorded CLI output.

Holehe interleaves a banner, progress bars and a trailing legend with its
results, and the legend line ("[+] Email used, [-] Email not used, ...") has
the same prefix as a real hit -- counting it inflated every measurement I took
before the parser required a domain shape.

The coverage caveat is the important one: even after the high-value allowlist,
many remaining sites refuse to answer, so an empty `services_found` beside a
non-zero `services_rate_limited` means "could not determine", not "no
accounts". These tests keep the two reported together. Niche sites
(dominos.fr, forums, adult, CRM) must not appear in `services_found`.

No subprocess is launched here; the recorded stdout is replayed.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import holehe_enricher as module  # noqa: E402
from holehe_enricher import HoleheEnricher  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "holehe"

pytestmark = pytest.mark.unit


def output(name):
    return (FIXTURES / f"{name}.txt").read_text()


class FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


@pytest.fixture
def enricher():
    scraper = HoleheEnricher(timeout=5)
    scraper.binary = "/fake/holehe"  # never actually executed
    return scraper


@pytest.fixture
def replay(monkeypatch):
    def install(fixture_name):
        monkeypatch.setattr(
            module.subprocess, "run",
            lambda *a, **kw: FakeCompleted(stdout=output(fixture_name)),
        )
    return install


class TestParsing:
    def test_finds_registered_services(self, enricher, replay):
        replay("found_gmail")
        result = enricher.enrich_email("jaoehring@gmail.com")
        assert result["status"] == "success"
        assert "twitter.com" in result["services_found"]
        assert "wordpress.com" in result["services_found"]

    def test_legend_line_is_not_a_service(self, enricher, replay):
        """
        Holehe prints "[+] Email used, [-] Email not used, [x] Rate limit" as a
        legend. It matched a naive [+] grep and inflated every count.
        """
        replay("found_gmail")
        found = enricher.enrich_email("a@b.com")["services_found"]
        assert len(found) == 7
        assert all("." in s and " " not in s for s in found)
        assert not any("email used" in s.lower() for s in found)

    def test_second_address_has_a_different_set(self, enricher, replay):
        replay("found_ringldr")
        found = enricher.enrich_email("james@ringldr.com")["services_found"]
        assert len(found) == 9
        assert "codepen.io" in found and "replit.com" in found

    def test_results_are_sorted_and_unique(self, enricher, replay):
        replay("found_ringldr")
        found = enricher.enrich_email("a@b.com")["services_found"]
        assert found == sorted(set(found))

    def test_counts_every_verdict(self, enricher, replay):
        replay("found_gmail")
        result = enricher.enrich_email("a@b.com")
        # High-value slice of the recorded 121-site run: 7 hits / 13 unused / 18 refused
        assert result["services_checked"] == 38
        assert result["services_rate_limited"] == 18

    def test_drops_niche_sites(self, enricher):
        stdout = (
            "[+] twitter.com\n"
            "[+] dominos.fr\n"
            "[+] pornhub.com\n"
            "[+] armurerie-auxerre.com\n"
            "[x] instagram.com\n"
        )
        parsed = HoleheEnricher.parse_output(stdout)
        assert parsed["services_found"] == ["twitter.com"]
        assert parsed["services_checked"] == 2
        assert parsed["services_rate_limited"] == 1


class TestCoverageHonesty:
    """
    Most sites refuse to answer, so absence of evidence is not evidence of
    absence -- the caller has to be able to tell the difference.
    """

    def test_rate_limited_count_is_reported(self, enricher, replay):
        replay("found_gmail")
        assert enricher.enrich_email("a@b.com")["services_rate_limited"] > 0

    def test_no_accounts_still_reports_refusals(self, enricher, replay):
        replay("no_accounts")
        result = enricher.enrich_email("nobody@gmail.com")
        assert result["services_found"] == []
        assert result["services_checked"] > 0
        assert result["services_rate_limited"] >= 15, (
            "an empty result must carry its refusal count, or it reads as "
            "'not registered anywhere'"
        )

    def test_control_address_yields_no_false_positives(self, enricher, replay):
        """A fabricated address returned zero hits against the live service."""
        replay("no_accounts")
        assert enricher.enrich_email("zzq8x7v3k2nonexistent9f4@gmail.com")["services_found"] == []

    def test_dormant_address_yields_nothing(self, enricher, replay):
        # rickioehring@yahoo.com: no accounts, yet 8 breaches in LeakCheck --
        # which is why breach lookup must not be gated on account hits
        replay("no_accounts_yahoo")
        assert enricher.enrich_email("rickioehring@yahoo.com")["services_found"] == []


class TestFailureModes:
    def test_empty_output_is_an_error_not_a_clean_result(self, enricher, monkeypatch):
        monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: FakeCompleted(stdout=""))
        result = enricher.enrich_email("a@b.com")
        assert result["status"] == "error"
        assert result["services_found"] == []

    def test_timeout_is_reported(self, enricher, monkeypatch):
        def boom(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="holehe", timeout=5)

        monkeypatch.setattr(module.subprocess, "run", boom)
        assert enricher.enrich_email("a@b.com")["status"] == "timeout"

    def test_missing_binary_is_reported(self):
        scraper = HoleheEnricher(timeout=5)
        scraper.binary = None
        result = scraper.enrich_email("a@b.com")
        assert result["status"] == "unavailable"
        assert "not found" in result["error"]

    @pytest.mark.parametrize("value", ["", "not-an-email", "a@b", "@b.com"])
    def test_invalid_addresses_never_run_the_cli(self, enricher, monkeypatch, value):
        def boom(*a, **kw):
            raise AssertionError("should not have run holehe")

        monkeypatch.setattr(module.subprocess, "run", boom)
        assert enricher.enrich_email(value)["status"] == "invalid_email"


class TestBinaryResolution:
    def test_prefers_env_override(self, monkeypatch, tmp_path):
        fake = tmp_path / "holehe"
        fake.write_text("#!/bin/sh\n")
        fake.chmod(0o755)
        monkeypatch.setenv("HOLEHE_BIN", str(fake))
        assert HoleheEnricher._find_binary() == str(fake)

    def test_reports_unavailable_when_nothing_found(self, monkeypatch):
        monkeypatch.delenv("HOLEHE_BIN", raising=False)
        monkeypatch.setattr(module.shutil, "which", lambda name: None)
        monkeypatch.setattr(module.Path, "is_file", lambda self: False)
        assert HoleheEnricher._find_binary() is None
