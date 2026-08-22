# targets/fps/models.py
"""
Data models for FPS scraper output.
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
    age: Optional[int] = None
    phone: str = ""
    profileUrl: str = ""
    email: str = ""
    aliases: str = ""
    relatives: str = ""


@dataclass
class Profile:
    """Full person profile"""
    profileId: str = ""
    fullName: str = ""
    age: Optional[int] = None
    bornDate: str = ""  # e.g. "June 1965" -- month/year only, FPS never gives a day
    aliases: List[str] = field(default_factory=list)
    currentAddress: Dict[str, str] = field(default_factory=dict)
    previousAddresses: List[Dict[str, str]] = field(default_factory=list)
    phoneNumbers: List[Dict[str, str]] = field(default_factory=list)
    emailAddresses: List[str] = field(default_factory=list)
    # Associates are folded in here too, each tagged "source": "relative" or
    # "associate" -- displayed as one family & friends list, the user sorts
    # out who's who during onboarding rather than the scraper guessing.
    relatives: List[Dict[str, str]] = field(default_factory=list)
    properties: List[Dict[str, Any]] = field(default_factory=list)
    employment: List[Dict[str, str]] = field(default_factory=list)
    jobHistory: List[Dict[str, str]] = field(default_factory=list)
    education: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScrapeOutput:
    """Standard output from scraper.run()"""
    source: str  # 'fps'
    search_params: Dict[str, Any]
    summary_results: List[SummaryResult] = field(default_factory=list)
    profile: Optional[Profile] = None
    timestamp: str = ""
    execution_time_ms: int = 0
    status: str = "pending"  # 'success', 'partial', 'failed', 'no_results'
    error: Optional[str] = None

