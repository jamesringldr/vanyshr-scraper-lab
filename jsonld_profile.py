"""
Shared JSON-LD Person helpers for the full-profile scrapers.

FPS and NPD both publish a schema.org Person block on their profile pages
carrying the name, addresses, phones and relatives. Reading that block is far
safer than regexing the rendered page: a phone pattern run over raw HTML also
matches profile-URL ids and form placeholders, which is how the previous
implementation produced numbers like (369) 730-5023 -- digits taken straight
out of /james-oehring_id_G3697305023830937972 -- and (626) 555-5555, lifted
from a placeholder attribute.

Note: npd_html_scraper carries near-identical helpers for the summary page.
They are left alone here to avoid churning tested code; worth consolidating
when the summary and profile paths next get touched together.
"""

import json
import logging
import re
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PHONE_DIGITS = re.compile(r'\D')


def _unescape_deep(value: Any) -> Any:
    """
    Recursively HTML-unescape every string in a parsed JSON-LD value.

    FPS embeds names with entities left un-decoded when they contain an
    apostrophe -- "O&#039;Connor" instead of "O'Connor" -- straight in the
    JSON-LD, a bug on their end that JSON parsing alone doesn't fix (HTML-
    escaping and JSON-escaping are separate layers). Decoding once here,
    covering the whole Person block (name, relatives, addresses, ...) rather
    than patching each field at each call site.
    """
    if isinstance(value, str):
        return unescape(value)
    if isinstance(value, list):
        return [_unescape_deep(v) for v in value]
    if isinstance(value, dict):
        return {k: _unescape_deep(v) for k, v in value.items()}
    return value


def extract_person(html: str) -> Optional[Dict[str, Any]]:
    """Return the first schema.org Person object on the page, if any."""
    soup = BeautifulSoup(html, 'html.parser')

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        # Some pages nest their entities under @graph
        for candidate in list(candidates):
            if isinstance(candidate, dict) and isinstance(candidate.get('@graph'), list):
                candidates.extend(candidate['@graph'])

        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get('@type') == 'Person':
                return _unescape_deep(candidate)

    return None


def extract_all_persons(html: str) -> List[Dict[str, Any]]:
    """
    Return every top-level schema.org Person object on the page, in document
    order -- for pages like Zaba's that can list more than one person (e.g.
    "More than 1 record found for Lucas Clark"), where extract_person()'s
    first-match behaviour would only ever see the first one.
    """
    soup = BeautifulSoup(html, 'html.parser')
    people: List[Dict[str, Any]] = []

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for candidate in list(candidates):
            if isinstance(candidate, dict) and isinstance(candidate.get('@graph'), list):
                candidates.extend(candidate['@graph'])

        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get('@type') == 'Person':
                people.append(_unescape_deep(candidate))

    return people


def format_phone(raw: Any) -> str:
    """Normalise a phone value to (XXX) XXX-XXXX, or "" if it isn't one."""
    digits = PHONE_DIGITS.sub('', str(raw or ""))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def format_phones(values: Any, limit: int = 10) -> List[Dict[str, str]]:
    """
    Turn a JSON-LD telephone value into phone dicts.

    FPS publishes already-formatted numbers, NPD publishes bare digits; both
    normalise to the same shape so dedup can compare across brokers.
    """
    if not values:
        return []
    if isinstance(values, (str, int)):
        values = [values]

    phones: List[Dict[str, str]] = []
    seen = set()
    for value in values:
        number = format_phone(value)
        if number and number not in seen:
            seen.add(number)
            phones.append({"number": number, "type": "unknown"})
    return phones[:limit]


def place_to_address(place: Any) -> Dict[str, str]:
    """Flatten a schema.org Place into an address dict."""
    if not isinstance(place, dict):
        return {}

    address = place.get('address')
    if not isinstance(address, dict):
        return {}

    street = (address.get('streetAddress') or "").strip()
    city = (address.get('addressLocality') or "").strip()
    region = (address.get('addressRegion') or "").strip()
    postal = (address.get('postalCode') or "").strip()

    locality = " ".join(p for p in (city, region, postal) if p)
    formatted = ", ".join(p for p in (street, locality) if p)

    result = {
        "street": street,
        "city": city,
        "state": region,
        "postalCode": postal,
        "formatted": formatted,
    }

    geo = place.get('geo')
    if isinstance(geo, dict):
        if geo.get('latitude'):
            result["latitude"] = str(geo['latitude'])
        if geo.get('longitude'):
            result["longitude"] = str(geo['longitude'])

    return {k: v for k, v in result.items() if v}


def split_home_locations(value: Any) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """
    Split a homeLocation value into (current, previous).

    The description field marks which is which ("Current home address" vs
    "Previous address"); when absent, the first entry is treated as current.
    """
    if not value:
        return {}, []
    places = [p for p in (value if isinstance(value, list) else [value]) if isinstance(p, dict)]
    if not places:
        return {}, []

    current: Dict[str, str] = {}
    previous: List[Dict[str, str]] = []

    for place in places:
        description = (place.get('description') or "").lower()
        address = place_to_address(place)
        if not address:
            continue
        if not current and ('current' in description or 'recent' in description or not description):
            current = address
        else:
            previous.append(address)

    if not current and previous:
        current = previous.pop(0)

    return current, previous


def related_names(value: Any, limit: int = 10) -> List[Dict[str, str]]:
    """Extract names from a relatedTo list."""
    if not value:
        return []
    names: List[Dict[str, str]] = []
    seen = set()
    for entry in (value if isinstance(value, list) else [value]):
        name = entry.get('name') if isinstance(entry, dict) else entry
        name = (name or "").strip() if isinstance(name, str) else ""
        if name and name not in seen:
            seen.add(name)
            names.append({"name": name})
    return names[:limit]


def age_from_birth_date(value: Any) -> Optional[int]:
    """Derive an age from a birthDate that may be just a year."""
    from datetime import datetime

    match = re.search(r'\d{4}', str(value or ""))
    if not match:
        return None
    age = datetime.now().year - int(match.group(0))
    return age if 0 < age < 150 else None
