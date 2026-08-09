# targets/hudson-rock/email/models.py
"""
Data models for Hudson Rock Email Search output.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ScrapeOutput:
    """Standard output from scraper.run()"""
    source: str  # 'hudson-rock-email'
    search_params: Dict[str, Any]
    breaches: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    execution_time_ms: int = 0
    status: str = "pending"  # 'success', 'not_found', 'rate_limited', 'error', 'failed'
    error: Optional[str] = None

