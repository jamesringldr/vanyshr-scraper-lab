# targets/npd/__init__.py
"""
NPD (National Public Data) Scraper Module

Pluggable scraper for vanyshr-mono app.

Usage:
    from targets.npd import run
    result = await run({
        'firstName': 'John',
        'lastName': 'Smith',
        'city': 'Denver',
        'state': 'CO'
    })
"""

from .scraper import run, NPDScraper
from .parser import NPDParser
from .models import ScrapeOutput, Profile, SummaryResult

__all__ = ['run', 'NPDScraper', 'NPDParser', 'ScrapeOutput', 'Profile', 'SummaryResult']

