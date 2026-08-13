# targets/zaba/models.py
"""
Data models for Zaba scraper output.
Using dataclasses for JSON serialization compatibility.

Note: Zaba returns all results on a single page as full profiles.
No summary/profile split like other targets.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class SummaryResult:
    """
    Single result, shaped like the other targets' summary rows so Zaba can take
    part in the Phase 1 sweep. Zaba fills these from the full profile it already
    returns, rather than from a separate summary page.
    """
    resultId: str
    fullName: str
    address: str
    age: Optional[int] = None
    profileUrl: str = ""
    phone: str = ""      # Comma-separated
    email: str = ""      # Comma-separated
    aliases: str = ""    # Comma-separated
    relatives: str = ""
    previousAddresses: str = ""  # Semicolon-separated former addresses


@dataclass
class Profile:
    """Full person profile (all results are full profiles on Zaba)"""
    profileId: str
    fullName: str
    age: Optional[int] = None
    currentAddress: Dict[str, str] = field(default_factory=dict)
    phoneNumbers: List[Dict[str, str]] = field(default_factory=list)
    emailAddresses: List[str] = field(default_factory=list)
    relatives: List[Dict[str, str]] = field(default_factory=list)
    associates: List[Dict[str, str]] = field(default_factory=list)
    properties: List[Dict[str, Any]] = field(default_factory=list)
    # Zaba-only extras, not published by the other three brokers
    aliases: List[str] = field(default_factory=list)
    pastAddresses: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ScrapeOutput:
    """Standard output from scraper.run()"""
    source: str  # 'zaba'
    search_params: Dict[str, Any]
    summary_results: List = field(default_factory=list)  # Empty - Zaba has no summary page
    profiles: List[Profile] = field(default_factory=list)  # All results as full profiles
    timestamp: str = ""
    execution_time_ms: int = 0
    status: str = "pending"  # 'success', 'partial', 'failed', 'no_results'
    error: Optional[str] = None

