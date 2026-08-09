# targets/leakcheck/__init__.py
"""
LeakCheck Email Breach Lookup Module

Pluggable scraper for vanyshr-mono app.
Checks if an email has been found in known data breaches via LeakCheck's free public API.

Usage:
    from targets.leakcheck import run
    result = await run({
        'email': 'user@example.com'
    })

Note: Uses LeakCheck's free public API (no authentication required)
"""

from .scraper import run, LeakCheckScraper
from .parser import LeakCheckParser
from .models import ScrapeOutput

__all__ = ['run', 'LeakCheckScraper', 'LeakCheckParser', 'ScrapeOutput']

