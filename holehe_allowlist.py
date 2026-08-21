"""High-value Holehe targets for Vanyshr account enrichment.

Holehe 1.61 ships 121 modules. Most are niche forums, FR-local shops, CRM
tools, or adult sites. Vanyshr only wants names a US consumer would recognize
on the pilot-scan "exposed accounts" hex.

This list is the probe allowlist (module function names) and the parse
allowlist (domains as holehe prints them). Keep them in lockstep.
"""

from __future__ import annotations

# holehe module __name__ -> domain string holehe prints on a result line.
HIGH_VALUE_TARGETS: dict[str, str] = {
    "adobe": "adobe.com",
    "amazon": "amazon.com",
    "anydo": "any.do",
    "archive": "archive.org",
    "codepen": "codepen.io",
    "discord": "discord.com",
    "docker": "docker.com",
    "ebay": "ebay.com",
    "envato": "envato.com",
    "eventbrite": "eventbrite.com",
    "evernote": "evernote.com",
    "firefox": "firefox.com",
    "flickr": "flickr.com",
    "freelancer": "freelancer.com",
    "github": "github.com",
    "google": "google.com",
    "gravatar": "en.gravatar.com",
    "imgur": "imgur.com",
    "instagram": "instagram.com",
    "lastfm": "last.fm",
    "lastpass": "lastpass.com",
    "nike": "nike.com",
    "office365": "office365.com",
    "patreon": "patreon.com",
    "pinterest": "pinterest.com",
    "protonmail": "protonmail.ch",
    "quora": "quora.com",
    "replit": "replit.com",
    "snapchat": "snapchat.com",
    "soundcloud": "soundcloud.com",
    "spotify": "spotify.com",
    "strava": "strava.com",
    "tumblr": "tumblr.com",
    "twitter": "twitter.com",
    "venmo": "venmo.com",
    "wordpress": "wordpress.com",
    "yahoo": "yahoo.com",
}

ALLOWED_MODULES = frozenset(HIGH_VALUE_TARGETS)

# Printed domains plus aliases the API / CLI have used.
ALLOWED_DOMAINS = frozenset(
    {
        *HIGH_VALUE_TARGETS.values(),
        "gravatar.com",
        "x.com",
        "protonmail.com",
        "proton.me",
        "dropbox.com",
        "facebook.com",
        "linkedin.com",
        "reddit.com",
        "medium.com",
        "stackoverflow.com",
        "gitlab.com",
    }
)


def normalize_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    if d.startswith("www.") or d.startswith("en."):
        d = d.split(".", 1)[1]
    return d


def is_high_value_domain(domain: str) -> bool:
    d = normalize_domain(domain)
    if d in ALLOWED_DOMAINS:
        return True
    # "github" from an API that keys by module name
    return d in ALLOWED_MODULES
