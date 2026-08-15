#!/usr/bin/env python3
"""
ZabaSearch HTML Scraper (context.dev HTML method)

Zaba publishes full profiles directly on the search page -- there is no
summary/profile split like FPS, NPD and AnyWho. One fetch yields name, age,
aliases, relatives, phones (with line type and carrier), emails, the current
address with county and coordinates, and past addresses.

Previously this module targeted https://search.zaba.com/search?q=...&where=...
and concluded Zaba blocks datacenter IPs. That was the wrong endpoint: it 400s
regardless of origin. The path-based www.zabasearch.com URL below scrapes
normally through context.dev, so no residential-IP fallback is needed.

Cost: ~0.001 per request
"""

import os
import sys
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from bs4 import BeautifulSoup
from context.dev import ContextDev

# targets/ models live alongside this module
sys.path.insert(0, str(Path(__file__).parent))

from targets.zaba.models import ScrapeOutput, SummaryResult, Profile

logger = logging.getLogger(__name__)


@dataclass
class ZabaHtmlScraperParams:
    """Parameters for Zaba HTML scraper"""
    firstName: str
    lastName: str
    city: str
    state: str
    timeout: int = 60


class ZabaHtmlScraper:
    """Zaba scraper using context.dev HTML method"""

    BASE_URL = "https://www.zabasearch.com"

    MAX_RESULTS = 5
    MAX_VALUES = 5

    STATE_NAMES = {
        "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
        "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
        "DC": "district-of-columbia", "FL": "florida", "GA": "georgia", "HI": "hawaii",
        "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa",
        "KS": "kansas", "KY": "kentucky", "LA": "louisiana", "ME": "maine",
        "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
        "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska",
        "NV": "nevada", "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico",
        "NY": "new-york", "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio",
        "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania", "RI": "rhode-island",
        "SC": "south-carolina", "SD": "south-dakota", "TN": "tennessee", "TX": "texas",
        "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington",
        "WV": "west-virginia", "WI": "wisconsin", "WY": "wyoming",
    }

    def __init__(self, timeout: int = 60, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not self.api_key:
            raise ValueError("CONTEXT_DEV_API_KEY environment variable not set")
        self.client = ContextDev(api_key=self.api_key, timeout=timeout)

    def _get_state_name(self, state: str) -> str:
        """Convert state abbr to the full lowercase name Zaba's URLs use"""
        return self.STATE_NAMES.get(state.upper(), state.lower().replace(" ", "-"))

    def _build_search_url(self, params: ZabaHtmlScraperParams) -> str:
        """
        Build Zaba search URL.

        Pattern: /people/{first}-{last}/{state-name}/{city}
        Example: /people/james-oehring/missouri/cameron
        """
        # Apostrophes (e.g. "Lee's Summit") break these sites' routing if left
        # in -- their own URLs drop the character rather than encoding it.
        first = params.firstName.strip().lower().replace(" ", "-").replace("'", "")
        last = params.lastName.strip().lower().replace(" ", "-").replace("'", "")
        state_name = self._get_state_name(params.state)
        city = params.city.strip().lower().replace(" ", "-").replace("'", "")

        return f"{self.BASE_URL}/people/{first}-{last}/{state_name}/{city}"

    # ---- parsing helpers -------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """Collapse whitespace."""
        return re.sub(r'\s+', ' ', text or "").strip()

    @classmethod
    def _section(cls, card, heading: str):
        """Find the section-box whose h3 matches `heading`."""
        for h3 in card.find_all(['h3', 'h4']):
            if heading.lower() in cls._clean(h3.get_text()).lower():
                return h3.parent
        return None

    @classmethod
    def _list_items(cls, card, heading: str) -> List[str]:
        """Text of every <li> under the section with the given heading."""
        section = cls._section(card, heading)
        if not section:
            return []
        items = []
        for li in section.find_all('li'):
            value = cls._clean(li.get_text())
            if value and value not in items:
                items.append(value)
        return items[: cls.MAX_VALUES]

    @staticmethod
    def _lines(element) -> List[str]:
        """Split an element's text on <br> into trimmed lines."""
        if not element:
            return []
        raw = element.get_text(separator='\n')
        return [ln.strip() for ln in raw.split('\n') if ln.strip()]

    def _parse_address(self, text_lines: List[str]) -> Dict[str, str]:
        """
        Turn ["413 Lovers LN", "Cameron, Missouri 64429"] into a dict.
        """
        if not text_lines:
            return {}
        street = text_lines[0]
        city = state = postal = ""
        if len(text_lines) > 1:
            match = re.match(r'^(.*?),\s*(.*?)\s+(\d{5}(?:-\d{4})?)$', text_lines[1])
            if match:
                city, state, postal = (g.strip() for g in match.groups())
            else:
                city = text_lines[1]
        return {
            "street": street,
            "city": city,
            "state": state,
            "postalCode": postal,
            "formatted": ", ".join([p for p in (street, text_lines[1] if len(text_lines) > 1 else "") if p]),
        }

    def _parse_phones(self, card) -> List[Dict[str, str]]:
        """
        Zaba lists phones twice: bare numbers under "Associated Phone Numbers",
        and the same numbers under "Last Known Phone Numbers" annotated with
        line type, carrier and first-reported date. Merge into one list, keyed
        by number, keeping the annotations.
        """
        phones: Dict[str, Dict[str, str]] = {}

        section = self._section(card, "Associated Phone Numbers")
        if section:
            for li in section.find_all('li'):
                number = self._clean(li.get_text())
                if re.match(r'^\(\d{3}\) \d{3}-\d{4}$', number):
                    phones[number] = {"number": number, "type": "", "carrier": "", "firstReported": ""}

        section = self._section(card, "Last Known Phone Numbers")
        if section:
            for h4 in section.find_all('h4'):
                heading = self._clean(h4.get_text())
                match = re.search(r'\(\d{3}\) \d{3}-\d{4}', heading)
                if not match:
                    continue
                number = match.group(0)
                entry = phones.setdefault(
                    number, {"number": number, "type": "", "carrier": "", "firstReported": ""}
                )
                entry["primary"] = "primary" in heading.lower()

                # The <p> siblings after the h4 carry: line type, carrier, and
                # optionally "First Reported <date>".
                for p in h4.find_next_siblings('p'):
                    value = self._clean(p.get_text())
                    if not value:
                        continue
                    reported = re.match(r'First Reported\s+(.*)$', value, re.IGNORECASE)
                    if reported:
                        entry["firstReported"] = reported.group(1)
                    elif value.lower() in ('mobile', 'landline', 'voip', 'unknown'):
                        # Zaba varies the casing between records ("Mobile" vs
                        # "mobile"); normalise so downstream grouping works.
                        entry["type"] = value.capitalize()
                    elif not entry["carrier"]:
                        entry["carrier"] = value.upper()

        return list(phones.values())[: self.MAX_VALUES]

    # Zaba usually withholds the email local part, substituting a run of literal
    # x's sized to the real value ("xxxxx@civicplus.com"). That is a teaser, not
    # an address: it parses as a valid email and would otherwise be stored as one.
    MASKED_LOCAL = re.compile(r'^x+$', re.IGNORECASE)

    def _parse_emails(self, card) -> List[str]:
        """
        Emails render as <span class="blur">local</span>@domain.com. The local
        part is styled blurred but its text is present, so plain extraction is
        enough (unlike AnyWho's data-content attributes) -- except when Zaba
        masks it, which is the common case.
        """
        section = self._section(card, "Associated Email Addresses")
        if not section:
            return []
        emails = []
        for li in section.find_all('li'):
            value = self._clean(li.get_text()).replace(' ', '')
            if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', value):
                continue
            if self.MASKED_LOCAL.match(value.split('@')[0]):
                logger.debug(f"Zaba: dropping masked email {value}")
                continue
            if value not in emails:
                emails.append(value)
        return emails[: self.MAX_VALUES]

    def _extract_profiles_from_html(self, html: str) -> List[Profile]:
        """Extract every person card on the page as a full Profile."""
        soup = BeautifulSoup(html, 'html.parser')
        profiles: List[Profile] = []

        for card in soup.select('div.person')[: self.MAX_RESULTS]:
            try:
                name_el = card.select_one('#container-name h2') or card.find('h2')
                full_name = self._clean(name_el.get_text()) if name_el else ""
                if not full_name:
                    continue

                age = None
                raw_age = card.get('data-age') or ""
                if not raw_age:
                    age_el = card.select_one('.container-age h3')
                    raw_age = self._clean(age_el.get_text()) if age_el else ""
                if raw_age.isdigit() and int(raw_age) < 150:
                    age = int(raw_age)

                # Current address, plus the county line and map coordinates
                current: Dict[str, str] = {}
                section = self._section(card, "Last Known Address")
                if section:
                    paragraphs = section.find_all('p')
                    if paragraphs:
                        current = self._parse_address(self._lines(paragraphs[0]))
                    if len(paragraphs) > 1:
                        current["county"] = self._clean(paragraphs[1].get_text())
                    map_el = section.find(class_='map')
                    if map_el:
                        if map_el.get('data-latitude'):
                            current["latitude"] = map_el['data-latitude']
                        if map_el.get('data-longitude'):
                            current["longitude"] = map_el['data-longitude']

                past = []
                section = self._section(card, "Past Addresses")
                if section:
                    for li in section.find_all('li')[: self.MAX_VALUES]:
                        parsed = self._parse_address(self._lines(li))
                        if parsed:
                            past.append(parsed)

                aliases = []
                alt = card.select_one('#container-alt-names')
                if alt:
                    for li in alt.find_all('li'):
                        value = self._clean(li.get_text())
                        if value and value not in aliases:
                            aliases.append(value)

                profiles.append(Profile(
                    profileId=card.get('data-id', '') or f"zaba_{len(profiles)}",
                    fullName=full_name,
                    age=age,
                    currentAddress=current,
                    phoneNumbers=self._parse_phones(card),
                    emailAddresses=self._parse_emails(card),
                    relatives=[{"name": n} for n in self._list_items(card, "Possible Relatives")],
                    aliases=aliases[: self.MAX_VALUES],
                    pastAddresses=past,
                ))

            except Exception as e:
                logger.warning(f"Error parsing Zaba person card: {e}")
                continue

        return profiles

    @staticmethod
    def _to_summary(profile: Profile, index: int) -> SummaryResult:
        """Flatten a Profile into the summary shape the sequence expects."""
        return SummaryResult(
            resultId=profile.profileId or f"zaba_{index}",
            fullName=profile.fullName,
            address=profile.currentAddress.get('formatted', ''),
            age=profile.age,
            profileUrl="",
            phone=', '.join(p['number'] for p in profile.phoneNumbers),
            email=', '.join(profile.emailAddresses),
            aliases=', '.join(profile.aliases),
            relatives=', '.join(r['name'] for r in profile.relatives),
            # Zaba returns full profiles at Phase 1, so its address history is
            # available for matching without a second fetch.
            previousAddresses='; '.join(
                a.get('formatted', '') for a in profile.pastAddresses if a.get('formatted')
            ),
        )

    # ---- entry point -----------------------------------------------------

    def run(self, params: Dict[str, Any]) -> ScrapeOutput:
        """Scrape Zaba for the given person."""
        started = datetime.utcnow()
        scraper_params = ZabaHtmlScraperParams(**params)
        search_url = self._build_search_url(scraper_params)

        logger.info(f"Zaba HTML scrape: {scraper_params.firstName} {scraper_params.lastName}")
        logger.debug(f"Fetching {search_url}")

        def elapsed_ms():
            return int((datetime.utcnow() - started).total_seconds() * 1000)

        try:
            result = self.client.web.web_scrape_html(url=search_url)
        except Exception as e:
            # A 404 means Zaba holds no record for this name/city -- an ordinary
            # outcome, not a failure of the scraper.
            not_found = '404' in str(e) or 'NOT_FOUND' in str(e)
            logger.info(f"Zaba: {'no records' if not_found else 'scrape failed'}: {e}")
            return ScrapeOutput(
                source="zaba-html",
                search_params=asdict(scraper_params),
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=elapsed_ms(),
                status="no_results" if not_found else "failed",
                error=None if not_found else str(e),
            )

        html = getattr(result, 'html', None)
        if not html:
            return ScrapeOutput(
                source="zaba-html",
                search_params=asdict(scraper_params),
                timestamp=datetime.utcnow().isoformat() + "Z",
                execution_time_ms=elapsed_ms(),
                status="no_results",
            )

        profiles = self._extract_profiles_from_html(html)

        return ScrapeOutput(
            source="zaba-html",
            search_params=asdict(scraper_params),
            summary_results=[self._to_summary(p, i) for i, p in enumerate(profiles)],
            profiles=profiles,
            timestamp=datetime.utcnow().isoformat() + "Z",
            execution_time_ms=elapsed_ms(),
            status="success" if profiles else "no_results",
        )


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """Module-level entry point matching the other targets."""
    scraper = ZabaHtmlScraper(timeout=params.get("timeout", 60))
    return asdict(scraper.run(params))


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)
    output = ZabaHtmlScraper().run({
        "firstName": "James", "lastName": "Oehring", "city": "Cameron", "state": "MO",
    })
    print(json.dumps(asdict(output), indent=2, default=str))
