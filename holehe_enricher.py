#!/usr/bin/env python3
"""
Holehe Enricher — which online services an email address is registered with.

Holehe is an open-source CLI (github.com/megadose/holehe). There is no hosted
API: the previous version of this module called https://api.holehe.io, a
hostname that does not resolve, so account enrichment has never worked.

It probes sites using password-recovery behaviour and reports, per site:

    [+] registered   [-] not registered   [x] the site refused to answer

Vanyshr does not use the full 121-site catalog. `holehe_runner.py` runs only
the high-value allowlist in `holehe_allowlist.py` (~37 consumer sites), and
`parse_output` drops anything else so a stock CLI still cannot leak
dominos.fr onto the hex.

Measured behaviour (holehe 1.61, residential, 2026-08-13): a [+] is
trustworthy (fabricated address → 0 hits). [x] is not: github / snapchat /
pinterest / soundcloud / evernote raise before a verdict, and live probes
show those endpoints are now DataDome or rewritten SPAs — parser patches
do not recover them. The runner wraps those exceptions as refused.

Do not pass holehe's -T/--timeout flag: in 1.61 it makes every module fail
in under a second.

`services_rate_limited` is reported alongside hits. An empty
`services_found` next to a large refusal count means "could not determine",
never "this address is registered nowhere".
"""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from holehe_allowlist import is_high_value_domain

logger = logging.getLogger(__name__)


class HoleheEnricher:
    """Run the holehe CLI against email addresses."""

    # Result lines look like "[+] twitter.com". The trailing legend holehe
    # prints ("[+] Email used, [-] Email not used, [x] Rate limit") matches the
    # same prefix, so a domain shape is required to exclude it.
    RESULT_LINE = re.compile(r'^\[([+\-x])\]\s+([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\s*$')

    EMAIL = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

    ANSI = re.compile(r'\x1b\[[0-9;]*m')

    def __init__(self, timeout: int = 60, binary: Optional[str] = None):
        """
        Args:
            timeout: seconds to allow a single run before giving up
            binary: path to the holehe executable; falls back to $HOLEHE_BIN,
                    then the project venv, then PATH
        """
        self.timeout = timeout
        self.binary = binary or self._find_binary()
        if not self.binary:
            logger.warning(
                "holehe executable not found. Install it with "
                "`.venv-local/bin/pip install holehe` or set HOLEHE_BIN."
            )

    @staticmethod
    def _find_binary() -> Optional[str]:
        """Locate the holehe executable."""
        candidates = [
            os.environ.get("HOLEHE_BIN"),
            str(Path(__file__).parent / ".venv-local" / "bin" / "holehe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return candidate
        return shutil.which("holehe")

    @property
    def available(self) -> bool:
        return bool(self.binary)

    def _result(self, email: str, status: str, **extra) -> Dict[str, Any]:
        result = {
            "email": email,
            "status": status,
            "services_found": [],
            "services_checked": 0,
            "services_rate_limited": 0,
            "error": None,
        }
        result.update(extra)
        return result

    def enrich_email(self, email: str) -> Dict[str, Any]:
        """
        Check one address.

        Returns a dict with status one of: success, invalid_email, unavailable,
        timeout, error.

        On success, `services_found` lists the sites the address is registered
        with, and `services_rate_limited` says how many sites declined to
        answer -- read them together, since an empty list beside a large
        rate-limited count means "we could not tell", not "nothing found".
        """
        email = (email or "").strip().lower()

        if not self.EMAIL.match(email):
            return self._result(email, "invalid_email", error="Invalid email address")

        if not self.available:
            return self._result(email, "unavailable", error="holehe executable not found")

        try:
            completed = subprocess.run(
                self._argv(email),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"Holehe timed out for {email} after {self.timeout}s")
            return self._result(email, "timeout", error=f"Timed out after {self.timeout}s")
        except OSError as e:
            logger.error(f"Holehe failed to run for {email}: {e}")
            return self._result(email, "error", error=str(e))

        parsed = self.parse_output(completed.stdout or "")

        if not parsed["services_checked"]:
            # No parseable result lines: treat as a failure rather than
            # reporting an empty list as though the address were clean.
            detail = (completed.stderr or completed.stdout or "").strip()[:200]
            logger.error(f"Holehe returned no results for {email}: {detail!r}")
            return self._result(email, "error", error="No results parsed from holehe output")

        return self._result(
            email,
            "success",
            services_found=parsed["services_found"],
            services_checked=parsed["services_checked"],
            services_rate_limited=parsed["services_rate_limited"],
        )

    def _argv(self, email: str) -> List[str]:
        """Prefer the allowlisted runner when the venv python is next to the binary."""
        runner = Path(__file__).resolve().parent / "holehe_runner.py"
        if self.binary and runner.is_file():
            python = Path(self.binary).parent / "python3"
            if python.is_file():
                return [str(python), str(runner), email, "--no-color", "--no-clear"]
        return [self.binary, email, "--no-color", "--no-clear"]

    @classmethod
    def parse_output(cls, stdout: str) -> Dict[str, Any]:
        """
        Pull the per-site verdicts out of holehe's terminal output.

        Progress bars, the banner and the legend are all interleaved with the
        results, so lines are matched strictly. Niche sites are discarded even
        if a stock holehe binary was used.
        """
        found: List[str] = []
        checked = 0
        rate_limited = 0

        for raw_line in (stdout or "").splitlines():
            line = cls.ANSI.sub("", raw_line).strip()
            match = cls.RESULT_LINE.match(line)
            if not match:
                continue

            marker, service = match.groups()
            if not is_high_value_domain(service):
                continue

            checked += 1
            if marker == "+":
                if service not in found:
                    found.append(service)
            elif marker == "x":
                rate_limited += 1

        return {
            "services_found": sorted(found),
            "services_checked": checked,
            "services_rate_limited": rate_limited,
        }

    def enrich_emails_batch(self, emails: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Check several addresses in sequence.

        Each run takes seconds and probes the high-value allowlist, so callers
        should pass a shortlist rather than every address a scrape turned up.
        """
        return {email: self.enrich_email(email) for email in emails}


def main():
    """Check addresses from the command line."""
    import sys

    logging.basicConfig(level=logging.INFO)
    enricher = HoleheEnricher()
    print(f"holehe binary: {enricher.binary or 'NOT FOUND'}\n")

    for email in sys.argv[1:] or ["jaoehring@gmail.com"]:
        result = enricher.enrich_email(email)
        print(f"{email}: {result['status']}")
        if result["status"] == "success":
            print(
                f"  {len(result['services_found'])} accounts from "
                f"{result['services_checked'] - result['services_rate_limited']} sites "
                f"that answered ({result['services_rate_limited']} refused)"
            )
            for service in result["services_found"]:
                print(f"    {service}")


if __name__ == "__main__":
    main()
