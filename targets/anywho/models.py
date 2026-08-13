# targets/anywho/models.py
"""
Data models for Anywho scraper output.
Using dataclasses for JSON serialization compatibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class SummaryResult:
    """Single result from summary search"""
    resultId: str
    fullName: str
    address: str
    ageRange: str = ""
    location: str = ""
    profileUrl: str = ""
    phone: str = ""
    email: str = ""
    aliases: str = ""
    relatives: str = ""
    previousAddresses: str = ""  # Semicolon-separated former addresses


@dataclass
class Profile:
    """Full person profile"""
    profileId: str = ""
    fullName: str = ""
    age: Optional[int] = None
    currentAddress: Dict[str, str] = field(default_factory=dict)
    previousAddresses: List[Dict[str, str]] = field(default_factory=list)
    phoneNumbers: List[Dict[str, str]] = field(default_factory=list)
    emailAddresses: List[str] = field(default_factory=list)
    familyMembers: List[Dict[str, Any]] = field(default_factory=list)
    properties: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScrapeOutput:
    """Standard output from scraper.run()"""
    source: str  # 'anywho'
    search_params: Dict[str, Any]
    summary_results: List[SummaryResult] = field(default_factory=list)
    profile: Optional[Profile] = None
    timestamp: str = ""
    execution_time_ms: int = 0
    status: str = "pending"  # 'success', 'partial', 'failed', 'no_results'
    error: Optional[str] = None

