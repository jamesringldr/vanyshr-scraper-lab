#!/usr/bin/env python3
"""
Capture real broker search HTML into tests/fixtures/ so scraper tests run offline.

Each call costs ~$0.001 via context.dev. Re-run only when a broker changes its
markup; the committed fixtures are what the test suite reads.

Usage:
    python3 tests/capture_fixtures.py            # capture everything missing
    python3 tests/capture_fixtures.py --force    # re-capture even if present
    python3 tests/capture_fixtures.py anywho     # capture one broker
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env.local")

from anywho_html_scraper import AnyWhoHtmlScraper, AnyWhoHtmlScraperParams
from fps_html_scraper import FPSHtmlScraper, FPSHtmlScraperParams
from npd_html_scraper import NPDHtmlScraper, NPDHtmlScraperParams
from zaba_html_scraper import ZabaHtmlScraper, ZabaHtmlScraperParams

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"

# Real people from the 17-profile test set. oehring/ocker/rodgers are the ones
# with known-good expected values to assert against; inman has no AnyWho record
# and gives us the no-results shape.
CASES = [
    ("anywho", "james_oehring_mo", dict(firstName="James", lastName="Oehring", city="Cameron", state="MO")),
    ("anywho", "chris_rodgers_ks", dict(firstName="Chris", lastName="Rodgers", city="Shawnee", state="KS")),
    ("anywho", "no_results", dict(firstName="Claire", lastName="Inman", city="Prairie Village", state="KS")),
    ("fps", "james_oehring_mo", dict(firstName="James", lastName="Oehring", city="Cameron", state="MO")),
    ("fps", "chris_ocker_mo", dict(firstName="Christopher", lastName="Ocker", city="Columbia", state="MO")),
    ("fps", "lucas_clark_mo", dict(firstName="Lucas", lastName="Clark", city="Kansas City", state="MO")),
    # Zaba returns full profiles on the search page, so these double as the
    # full-profile fixtures.
    ("zaba", "james_oehring_mo", dict(firstName="James", lastName="Oehring", city="Cameron", state="MO")),
    ("zaba", "lucas_clark_mo", dict(firstName="Lucas", lastName="Clark", city="Kansas City", state="MO")),
    # Zaba has a record here even though AnyWho and NPD return nothing. There is
    # no no-results fixture: Zaba 404s for an unknown person, which run() maps
    # to status=no_results, so that path is tested against a stubbed client.
    ("zaba", "claire_inman_ks", dict(firstName="Claire", lastName="Inman", city="Prairie Village", state="KS")),
]

SCRAPERS = {
    "anywho": (AnyWhoHtmlScraper, AnyWhoHtmlScraperParams),
    "fps": (FPSHtmlScraper, FPSHtmlScraperParams),
    "npd": (NPDHtmlScraper, NPDHtmlScraperParams),
    "zaba": (ZabaHtmlScraper, ZabaHtmlScraperParams),
}


# Profile pages are captured by first parsing a saved summary fixture, taking
# the profile URL it yields, and fetching that. Keeps the profile fixtures in
# step with whatever the summary scrapers currently produce.
PROFILE_CASES = [
    ("fps", "james_oehring_mo"),
    ("fps", "lucas_clark_mo"),
    ("npd", "james_oehring_mo"),
    ("anywho", "james_oehring_mo"),
    ("anywho", "chris_rodgers_ks"),
]

PROFILE_BASE = {
    "fps": "https://www.fastpeoplesearch.com",
    "npd": "https://nationalpublicdata.com",
    "anywho": "https://www.anywho.com",
}


def summary_profile_url(broker: str, fixture: str):
    """Parse a saved summary fixture and return its first profile URL."""
    scraper_cls, _ = SCRAPERS[broker]
    scraper = scraper_cls(api_key=os.environ.get("CONTEXT_DEV_API_KEY", "x"))
    html = (FIXTURE_DIR / broker / f"{fixture}.html").read_text()
    results = scraper._extract_summary_from_html(html)
    if not results:
        return None
    url = getattr(results[0], "profileUrl", "")
    if url and not url.startswith("http"):
        url = PROFILE_BASE[broker] + url
    return url or None


def capture_profile(broker: str, fixture: str, force: bool = False) -> bool:
    out_dir = FIXTURE_DIR / broker
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{fixture}_profile.html"

    if out_path.exists() and not force:
        print(f"  skip    {broker}/{out_path.name} (exists)")
        return True

    url = summary_profile_url(broker, fixture)
    if not url:
        print(f"  SKIP    {broker}/{fixture}: summary yields no profile URL")
        return False

    scraper_cls, _ = SCRAPERS[broker]
    scraper = scraper_cls()
    try:
        result = scraper.client.web.web_scrape_html(url=url)
    except Exception as e:
        print(f"  FAIL    {broker}/{out_path.name}: {type(e).__name__}: {str(e)[:100]}")
        return False

    html = getattr(result, "html", None)
    if not html:
        print(f"  EMPTY   {broker}/{out_path.name}: no html from {url}")
        return False

    out_path.write_text(html)
    print(f"  saved   {broker}/{out_path.name}  ({len(html):,} bytes)  <- {url}")
    return True


def capture(broker: str, name: str, params: dict, force: bool = False) -> bool:
    out_dir = FIXTURE_DIR / broker
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.html"

    if out_path.exists() and not force:
        print(f"  skip    {broker}/{name}.html (exists)")
        return True

    scraper_cls, params_cls = SCRAPERS[broker]
    scraper = scraper_cls()
    url = scraper._build_search_url(params_cls(**params))

    try:
        result = scraper.client.web.web_scrape_html(url=url)
    except Exception as e:
        print(f"  FAIL    {broker}/{name}: {type(e).__name__}: {e}")
        return False

    html = getattr(result, "html", None)
    if not html:
        print(f"  EMPTY   {broker}/{name}: no html returned from {url}")
        return False

    out_path.write_text(html)
    print(f"  saved   {broker}/{name}.html  ({len(html):,} bytes)  <- {url}")
    return True


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv

    if "--profiles" in sys.argv:
        cases = [c for c in PROFILE_CASES if not args or c[0] in args]
        print(f"Capturing {len(cases)} profile fixture(s) into {FIXTURE_DIR}\n")
        ok = sum(capture_profile(b, f, force) for b, f in cases)
    else:
        cases = [c for c in CASES if not args or c[0] in args]
        print(f"Capturing {len(cases)} fixture(s) into {FIXTURE_DIR}\n")
        ok = sum(capture(b, n, p, force) for b, n, p in cases)

    print(f"\n{ok}/{len(cases)} captured")
    return 0 if ok == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
