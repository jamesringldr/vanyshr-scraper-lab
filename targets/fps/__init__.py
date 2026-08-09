# targets/fps/__init__.py
"""
FPS (FirstPoint Search) Scraper Module

Pluggable scraper for vanyshr-mono app.

Usage:
    from targets.fps import run
    result = await run({
        'firstName': 'John',
        'lastName': 'Smith',
        'city': 'Denver',
        'state': 'CO'
    })
"""

from .scraper import run, FPSScraper
from .parser import FPSParser
from .models import ScrapeOutput, Profile, SummaryResult

__all__ = ['run', 'FPSScraper', 'FPSParser', 'ScrapeOutput', 'Profile', 'SummaryResult']

