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

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env.local")

from anywho_html_scraper import AnyWhoHtmlScraper, AnyWhoHtmlScraperParams
from fps_html_scraper import FPSHtmlScraper, FPSHtmlScraperParams
from npd_html_scraper import NPDHtmlScraper, NPDHtmlScraperParams

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
]

SCRAPERS = {
    "anywho": (AnyWhoHtmlScraper, AnyWhoHtmlScraperParams),
    "fps": (FPSHtmlScraper, FPSHtmlScraperParams),
    "npd": (NPDHtmlScraper, NPDHtmlScraperParams),
}


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
    cases = [c for c in CASES if not args or c[0] in args]

    print(f"Capturing {len(cases)} fixture(s) into {FIXTURE_DIR}\n")
    ok = sum(capture(b, n, p, force) for b, n, p in cases)
    print(f"\n{ok}/{len(cases)} captured")
    return 0 if ok == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
