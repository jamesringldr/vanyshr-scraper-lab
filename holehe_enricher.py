#!/usr/bin/env python3
"""
Holehe Enricher — which online services an email address is registered with.

Holehe is an open-source CLI (github.com/megadose/holehe). There is no hosted
API: the previous version of this module called https://api.holehe.io, a
hostname that does not resolve, so account enrichment has never worked.

It probes ~121 sites using password-recovery behaviour and reports, per site:

    [+] registered   [-] not registered   [x] the site refused to answer

Measured behaviour (121 sites, holehe 1.61, from a residential connection):

  runtime          4-10s per address
  answered         ~46 of 121 sites (7 hits / 41 not-used / 74 refused)
  repeatability    identical hit and refusal sets across runs
  false positives  none -- a fabricated address returned zero hits

A [+] can therefore be trusted. The [x] marker cannot: holehe's runner wraps
each module in a bare `except Exception` and labels *every* failure "Rate
limit". Probing the failing modules directly shows two unrelated causes:

  - modules whose site changed shape, which fail deterministically
    (github and snapchat raise IndexError, pinterest JSONDecodeError)
  - modules that merely ran out of time in the 121-way concurrent burst;
    atlassian, amazon, imgur, instagram and adobe all answer normally when
    run on their own

So the refusals are stale modules and timeouts, not IP blocking -- the figures
above were measured from a residential connection, and a different host will
not improve them. Recovering that coverage means patching modules or lowering
concurrency, not changing where this runs.

Do not pass holehe's -T/--timeout flag: in 1.61 it makes every module fail
(120 refused in under a second).

Because ~62% of sites do not answer, `services_rate_limited` is reported
alongside the hits. An empty `services_found` next to a large refusal count
means "could not determine", never "this address is registered nowhere".
"""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

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
                [self.binary, email, "--no-color", "--no-clear"],
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

    @classmethod
    def parse_output(cls, stdout: str) -> Dict[str, Any]:
        """
        Pull the per-site verdicts out of holehe's terminal output.

        Progress bars, the banner and the legend are all interleaved with the
        results, so lines are matched strictly.
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

        Each run takes seconds and makes ~121 outbound requests, so callers
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
