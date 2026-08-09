# targets/holehe/models.py
"""
Data models for Holehe scraper output.
Using dataclasses for JSON serialization compatibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ServiceResult:
    """Result for a single service check"""
    service: str
    status: str  # 'found', 'not_found', 'rate_limit', 'error'
    email: str = ""
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ScrapeOutput:
    """Standard output from scraper.run()"""
    source: str  # 'holehe'
    search_params: Dict[str, Any]
    results: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)  # Counts by status
    timestamp: str = ""
    execution_time_ms: int = 0
    status: str = "pending"  # 'success', 'failed'
    error: Optional[str] = None

