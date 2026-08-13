#!/usr/bin/env python3
"""
LeakCheck Enricher — breach exposure for an email address.

Uses the free public endpoint, which needs no API key:

    https://leakcheck.io/api/public?check=<email>

It returns which breaches an address appears in, when, and which *types* of
field leaked -- never the leaked values themselves. That is the right shape for
showing someone their exposure without handling their credentials.

This endpoint has four behaviours worth knowing about, each of which this
module handles explicitly (see tests/fixtures/leakcheck/README.md):

  - HTTP status is always 200, including for misses and rate limiting, so the
    status code cannot be used to detect failure
  - the rate-limit body is not valid JSON -- it uses Python's `False` instead of
    `false`, so json.loads() raises exactly when the service is under load
  - a browser-like User-Agent is required or Cloudflare returns 403
  - invalid addresses return the same body as genuine misses

Previously this module targeted https://leakcheck.io/api/v2/query, the paid
tier, and returned nothing without LEAKCHECK_API_KEY set.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LeakcheckEnricher:
    """Look up breach exposure for email addresses."""

    API_URL = "https://leakcheck.io/api/public"

    # Cloudflare rejects requests without a browser-like agent
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # The quota is roughly ten calls per window; batches pace themselves to
    # stay under it rather than discovering the limit by tripping over it.
    DEFAULT_BATCH_DELAY = 7.0

    EMAIL = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """
        Args:
            api_key: unused; kept so existing callers do not break. The public
                     endpoint takes no credentials.
            timeout: HTTP timeout in seconds
        """
        self.timeout = timeout
        if api_key:
            logger.debug("LeakcheckEnricher: api_key ignored, public endpoint takes none")

    # ---- response handling ----------------------------------------------

    @staticmethod
    def _loads(body: str) -> Optional[Dict[str, Any]]:
        """
        Parse a response body, tolerating the rate-limit reply's invalid JSON.

        The rate-limit case is served as {"success": False, ...} -- Python's
        capitalised False, which json.loads rejects. Rather than let that crash
        the caller, retry once with the literal corrected.
        """
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            pass

        repaired = re.sub(r'\bFalse\b', 'false', body)
        repaired = re.sub(r'\bTrue\b', 'true', repaired)
        repaired = re.sub(r'\bNone\b', 'null', repaired)
        try:
            return json.loads(repaired)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Leakcheck: unparseable response: {body[:120]!r}")
            return None

    @classmethod
    def _is_rate_limited(cls, data: Optional[Dict[str, Any]], body: str) -> bool:
        error = (data or {}).get("error", "") if isinstance(data, dict) else ""
        haystack = f"{error} {body}".lower()
        return "ratelimit" in haystack or "too many requests" in haystack

    def _result(self, email: str, status: str, **extra) -> Dict[str, Any]:
        result = {
            "email": email,
            "status": status,
            "breaches": [],
            "breach_count": 0,
            "fields_exposed": [],
            "error": None,
        }
        result.update(extra)
        return result

    # ---- public API ------------------------------------------------------

    def enrich_email(self, email: str) -> Dict[str, Any]:
        """
        Look up one address.

        Returns a dict with status one of: success, not_found, invalid_email,
        rate_limited, timeout, error. Breaches are only present on success.
        """
        email = (email or "").strip().lower()

        # An invalid address returns the same body as a genuine miss, so screen
        # it here to keep the two distinguishable downstream.
        if not self._is_valid_email(email):
            logger.debug(f"Leakcheck: skipping invalid address {email!r}")
            return self._result(email, "invalid_email", error="Invalid email address")

        try:
            response = httpx.get(
                self.API_URL,
                params={"check": email},
                headers={"User-Agent": self.USER_AGENT, "Accept": "application/json"},
                timeout=self.timeout,
                follow_redirects=True,
            )
        except httpx.TimeoutException:
            logger.warning(f"Leakcheck timeout for {email}")
            return self._result(email, "timeout", error="Request timed out")
        except httpx.HTTPError as e:
            logger.error(f"Leakcheck request failed for {email}: {e}")
            return self._result(email, "error", error=str(e))

        body = response.text or ""
        data = self._loads(body)

        if self._is_rate_limited(data, body):
            logger.warning(f"Leakcheck rate limited on {email}")
            return self._result(email, "rate_limited", error="Rate limited")

        if data is None:
            return self._result(email, "error", error="Unparseable response")

        # Status is 200 even for failures, so the body decides.
        if not data.get("success"):
            return self._result(email, "not_found")

        breaches = self._parse_sources(data.get("sources"))
        fields = [f for f in (data.get("fields") or []) if isinstance(f, str)]

        return self._result(
            email,
            "success",
            breaches=breaches,
            # Trust the reported count over len(sources); they can differ when
            # the API withholds some source names.
            breach_count=data.get("found") if isinstance(data.get("found"), int) else len(breaches),
            fields_exposed=sorted(set(fields)),
        )

    def enrich_emails_batch(
        self,
        emails: List[str],
        delay: Optional[float] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Look up several addresses, pacing calls to stay inside the quota.

        Stops early once rate limited: continuing would only return more
        rate-limit responses and mask which addresses were genuinely checked.
        """
        delay = self.DEFAULT_BATCH_DELAY if delay is None else delay
        results: Dict[str, Dict[str, Any]] = {}

        for index, email in enumerate(emails):
            if index:
                time.sleep(delay)

            result = self.enrich_email(email)
            results[email] = result

            if result["status"] == "rate_limited":
                logger.warning(
                    f"Leakcheck rate limited after {index} of {len(emails)} addresses; "
                    f"stopping so the remainder are not misreported as checked"
                )
                break

        return results

    @classmethod
    def _parse_sources(cls, sources: Any) -> List[Dict[str, str]]:
        """Normalise the sources list into {source, date, year} records."""
        if not isinstance(sources, list):
            return []

        breaches: List[Dict[str, str]] = []
        seen = set()
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)

            date = (entry.get("date") or "").strip()
            year = date[:4] if re.match(r'^\d{4}', date) else ""
            breaches.append({"source": name, "date": date, "year": year})

        # Most recent first: an old breach matters less than a recent one
        return sorted(breaches, key=lambda b: b["date"], reverse=True)

    @classmethod
    def _is_valid_email(cls, email: str) -> bool:
        return bool(email) and bool(cls.EMAIL.match(email))


def main():
    """Check a couple of addresses from the command line."""
    import sys

    logging.basicConfig(level=logging.INFO)
    enricher = LeakcheckEnricher()

    emails = sys.argv[1:] or ["jaoehring@gmail.com"]
    for email in emails:
        result = enricher.enrich_email(email)
        print(f"\n{email}: {result['status']}")
        if result["status"] == "success":
            print(f"  {result['breach_count']} breaches")
            print(f"  exposed: {', '.join(result['fields_exposed'])}")
            for breach in result["breaches"]:
                print(f"    {breach['date']}  {breach['source']}")


if __name__ == "__main__":
    main()
