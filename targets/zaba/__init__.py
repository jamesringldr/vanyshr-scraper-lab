# targets/zaba/__init__.py
"""
Zaba Scraper Module

Pluggable scraper for vanyshr-mono app.

Usage:
    from targets.zaba import run
    result = await run({
        'firstName': 'John',
        'lastName': 'Smith',
        'city': 'Denver',
        'state': 'CO'
    })

Note: Zaba returns all results as full profiles on a single page (no summary/profile split).
"""

from .scraper import run, ZabaScraper
from .parser import ZabaParser
from .models import ScrapeOutput, Profile

__all__ = ['run', 'ZabaScraper', 'ZabaParser', 'ScrapeOutput', 'Profile']

