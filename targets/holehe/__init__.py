# targets/holehe/__init__.py
"""
Holehe Email Scraper Module

Pluggable scraper for vanyshr-mono app.
Checks if an email has been exposed across online services.

Usage:
    from targets.holehe import run
    result = await run({
        'email': 'user@example.com',
        'timeout': 10
    })
"""

from .scraper import run, HoleheScraper
from .parser import HoleheParser
from .models import ScrapeOutput, ServiceResult

__all__ = ['run', 'HoleheScraper', 'HoleheParser', 'ScrapeOutput', 'ServiceResult']

