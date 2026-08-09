# targets/hibp/models.py
"""
Data models for HIBP scraper output.
Using dataclasses for JSON serialization compatibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ScrapeOutput:
    """Standard output from scraper.run()"""
    source: str  # 'hibp'
    search_params: Dict[str, Any]
    breaches: List[Dict[str, Any]] = field(default_factory=list)
    pastes: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    execution_time_ms: int = 0
    status: str = "pending"  # 'success', 'not_found', 'rate_limited', 'error'
    error: Optional[str] = None

