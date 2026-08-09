# targets/hibp/__init__.py
"""
HIBP (Have I Been Pwned) Email Breach Lookup Module

Pluggable scraper for vanyshr-mono app.
Checks if an email has been found in known data breaches.

Usage:
    from targets.hibp import run
    result = await run({
        'email': 'user@example.com',
        'apiKey': 'your-hibp-api-key'
    })

Note: Requires API key from haveibeenpwned.com
"""

from .scraper import run, HibpScraper
from .parser import HibpParser
from .models import ScrapeOutput

__all__ = ['run', 'HibpScraper', 'HibpParser', 'ScrapeOutput']

