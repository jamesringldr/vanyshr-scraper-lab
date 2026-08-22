# targets/npd/models.py
"""
Data models for NPD scraper output.
Using dataclasses for JSON serialization compatibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class SummaryResult:
    """Single result from summary search"""
    resultId: str
    fullName: str
    addressPreview: str
    phonePreview: str = ""
    matchScore: int = 0
    profileUrl: str = ""
    ageRange: str = ""
    email: str = ""
    aliases: str = ""
    relatives: str = ""


@dataclass
class Address:
    """Address record"""
    street: str
    city: str
    state: str
    postalCode: str = ""
    formatted: str = ""
    yearsActive: str = ""
    addressType: str = "current"


@dataclass
class Contact:
    """Phone or email contact"""
    contactType: str  # 'phone' or 'email'
    contactValue: str
    phoneType: str = ""  # 'mobile', 'landline', 'voip'
    status: str = "current"


@dataclass
class Relative:
    """Family member"""
    name: str
    relationship: str
    address: str = ""


@dataclass
class Property:
    """Real estate property"""
    address: str
    propertyType: str
    yearBuilt: Optional[int] = None
    estimatedValue: Optional[int] = None


@dataclass
class Profile:
    """Full person profile"""
    profileId: str = ""
    fullName: str = ""
    dateOfBirth: Optional[str] = None
    age: Optional[int] = None
    currentAddress: Dict[str, str] = field(default_factory=dict)
    previousAddresses: List[Dict[str, str]] = field(default_factory=list)
    phoneNumbers: List[Dict[str, str]] = field(default_factory=list)
    emailAddresses: List[str] = field(default_factory=list)
    relatives: List[Dict[str, str]] = field(default_factory=list)
    associates: List[Dict[str, str]] = field(default_factory=list)
    properties: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScrapeOutput:
    """Standard output from scraper.run()"""
    source: str  # 'npd'
    search_params: Dict[str, Any]
    summary_results: List[SummaryResult] = field(default_factory=list)
    profile: Optional[Profile] = None
    timestamp: str = ""
    execution_time_ms: int = 0
    status: str = "pending"  # 'success', 'partial', 'failed', 'no_results'
    error: Optional[str] = None

