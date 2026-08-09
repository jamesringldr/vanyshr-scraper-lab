# targets/hudson-rock/email/__init__.py
"""
Hudson Rock Email Search Module

Searches infostealer databases for credentials associated with email addresses.

Usage:
    from targets.hudson_rock.email import run
    result = await run({
        'email': 'user@example.com',
        'apiKey': 'your-hudson-rock-api-key'
    })
"""

from .scraper import run, HudsonRockEmailScraper
from .parser import HudsonRockEmailParser
from .models import ScrapeOutput

__all__ = ['run', 'HudsonRockEmailScraper', 'HudsonRockEmailParser', 'ScrapeOutput']

