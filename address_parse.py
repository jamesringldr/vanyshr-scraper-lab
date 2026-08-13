"""
Address parsing shared by the dedup engine and the display models.

The four scrapers emit four different shapes, and the difference matters:
splitting on commas and taking the first segment as the city was correct while
addresses looked like "Cameron, MO", but silently became wrong once the
scrapers began returning full street addresses -- yielding city='413 Lovers Ln'.

Lives in its own module because both dedup_engine (for matching) and
data_models (for the display fields written to quickscan_dedup_groups) need it,
and dedup_engine already imports data_models.
"""

import re
from typing import Dict

# Full state names to abbreviations, so "Missouri" and "MO" compare equal.
# Zaba writes the name, the other three write the abbreviation.
STATE_ABBR = {
    'alabama': 'al', 'alaska': 'ak', 'arizona': 'az', 'arkansas': 'ar',
    'california': 'ca', 'colorado': 'co', 'connecticut': 'ct', 'delaware': 'de',
    'district of columbia': 'dc', 'florida': 'fl', 'georgia': 'ga', 'hawaii': 'hi',
    'idaho': 'id', 'illinois': 'il', 'indiana': 'in', 'iowa': 'ia',
    'kansas': 'ks', 'kentucky': 'ky', 'louisiana': 'la', 'maine': 'me',
    'maryland': 'md', 'massachusetts': 'ma', 'michigan': 'mi', 'minnesota': 'mn',
    'mississippi': 'ms', 'missouri': 'mo', 'montana': 'mt', 'nebraska': 'ne',
    'nevada': 'nv', 'new hampshire': 'nh', 'new jersey': 'nj', 'new mexico': 'nm',
    'new york': 'ny', 'north carolina': 'nc', 'north dakota': 'nd', 'ohio': 'oh',
    'oklahoma': 'ok', 'oregon': 'or', 'pennsylvania': 'pa', 'rhode island': 'ri',
    'south carolina': 'sc', 'south dakota': 'sd', 'tennessee': 'tn', 'texas': 'tx',
    'utah': 'ut', 'vermont': 'vt', 'virginia': 'va', 'washington': 'wa',
    'west virginia': 'wv', 'wisconsin': 'wi', 'wyoming': 'wy',
}

# Secondary address lines, which sit between the street and the city and would
# otherwise be mistaken for one or the other.
UNIT_PREFIXES = ('apt', 'unit', 'ste', 'suite', '#', 'apartment', 'fl', 'floor')


def parse_address(raw: str) -> Dict[str, str]:
    """
    Split an address into street, city, state and postal code, lowercased.

    Parsed from the right, because that end is predictable while the left is
    not. The shapes in use:

        413 Lovers Ln, Cameron MO 64429              street, "city ST zip"
        413 Lovers Ln, Cameron, MO                   street, city, ST
        1225 Union Ave, Apt 502, Kansas City, MO     street, unit, city, ST
        413 Lovers LN, Cameron, Missouri 64429       street, city, "State zip"
    """
    blank = {"street": "", "city": "", "state": "", "postal": ""}
    if not raw or not raw.strip():
        return blank

    parts = [p.strip() for p in raw.split(',') if p.strip()]
    if not parts:
        return blank

    tail = parts.pop().lower()

    postal = ""
    match = re.search(r'\b(\d{5})(?:-\d{4})?$', tail)
    if match:
        postal = match.group(1)
        tail = tail[:match.start()].strip()

    state = ""
    if tail in STATE_ABBR:
        state, tail = STATE_ABBR[tail], ""
    elif re.fullmatch(r'[a-z]{2}', tail):
        state, tail = tail, ""
    else:
        for full, abbr in STATE_ABBR.items():
            if tail.endswith(' ' + full):
                state, tail = abbr, tail[: -len(full) - 1].strip()
                break
        else:
            match = re.search(r'\b([a-z]{2})$', tail)
            if match and match.group(1) in STATE_ABBR.values():
                state, tail = match.group(1), tail[: match.start()].strip()

    city = tail
    if not city and parts:
        city = parts.pop().lower()

    # Unit lines are not city names
    while city and city.split()[0].rstrip('.') in UNIT_PREFIXES and parts:
        city = parts.pop().lower()

    return {
        "street": ", ".join(parts).lower(),
        "city": city.strip(),
        "state": state,
        "postal": postal,
    }
