# targets/hudson-rock/username/__init__.py
"""
Hudson Rock Username Search Module

Searches infostealer databases for credentials associated with usernames.

Usage:
    from targets.hudson_rock.username import run
    result = await run({
        'username': 'john_doe',
        'apiKey': 'your-hudson-rock-api-key'
    })
"""

from .scraper import run, HudsonRockUsernameScraper
from .parser import HudsonRockUsernameParser
from .models import ScrapeOutput

__all__ = ['run', 'HudsonRockUsernameScraper', 'HudsonRockUsernameParser', 'ScrapeOutput']

