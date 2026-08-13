"""
Data models for sequence runner.
Defines all dataclasses used throughout the system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

from address_parse import parse_address


class BrokerName(str, Enum):
    """Supported brokers"""
    FPS = "fps"
    NPD = "npd"
    ANYWHO = "anywho"
    ZABA = "zaba"


@dataclass
class SummaryResult:
    """Single summary result from a broker"""
    broker: BrokerName
    full_name: str
    # The broker's own id for this result. Zaba uses it to match a Phase 1
    # summary back to the full profile it returned at the same time.
    result_id: str = ""
    address: str = ""
    age_range: str = ""  # e.g., "37", "Age 37", empty if not available
    age: Optional[int] = None  # Parsed integer
    location: str = ""
    profile_url: str = ""
    phone: str = ""  # Comma-separated phone numbers
    email: str = ""  # Comma-separated emails
    aliases: str = ""  # Comma-separated aliases/AKAs
    relatives: str = ""  # Comma-separated relative names
    # Semicolon-separated former addresses. Matching on these matters: brokers
    # disagree about which address is current, and a prior address is often the
    # only thing linking one broker's record to another's.
    previous_addresses: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON"""
        return {
            'broker': self.broker.value,
            'result_id': self.result_id,
            'full_name': self.full_name,
            'address': self.address,
            'age_range': self.age_range,
            'age': self.age,
            'location': self.location,
            'profile_url': self.profile_url,
            'phone': self.phone,
            'email': self.email,
            'aliases': self.aliases,
            'relatives': self.relatives,
            'previous_addresses': self.previous_addresses,
        }


@dataclass
class DedupMember:
    """Member of a dedup group (one broker's match)"""
    summary: SummaryResult
    match_score: float  # 0-100

    def to_dict(self) -> dict:
        return {
            'broker': self.summary.broker.value,
            'summary': self.summary.to_dict(),
            'match_score': self.match_score,
        }


@dataclass
class DedupGroup:
    """Group of matched summaries (same person from different brokers)"""
    dedup_id: str  # Unique ID for this group (hash of name, city, state)
    members: List[DedupMember] = field(default_factory=list)

    # Metadata
    age_conflict: bool = False  # Age differs by > 3 years
    age_note: Optional[str] = None  # e.g., "Most sources say 37, one says 61"

    def add_member(self, summary: SummaryResult, match_score: float):
        """Add a member to this group"""
        self.members.append(DedupMember(summary, match_score))

    @property
    def average_confidence(self) -> float:
        """Average match score across all members"""
        if not self.members:
            return 0.0
        return sum(m.match_score for m in self.members) / len(self.members)

    @property
    def primary_name(self) -> str:
        """Get name from first member (representative)"""
        return self.members[0].summary.full_name if self.members else ""

    @property
    def primary_city(self) -> str:
        """
        City of the first member.

        Parsed rather than split on commas: with full street addresses the old
        heuristic returned the street, so this field reached the database as
        "413 Lovers Ln".
        """
        if not self.members:
            return ""
        return parse_address(self.members[0].summary.address)["city"].title()

    @property
    def primary_state(self) -> str:
        """State of the first member, as a two-letter abbreviation."""
        if not self.members:
            return ""
        return parse_address(self.members[0].summary.address)["state"].upper()

    def resolve_age(self) -> Optional[int]:
        """Get most common age (median)"""
        ages = [m.summary.age for m in self.members if m.summary.age]
        if not ages:
            return None
        return sorted(ages)[len(ages) // 2]

    def get_sources(self) -> List[str]:
        """Get list of broker sources"""
        return [m.summary.broker.value for m in self.members]

    def to_display(self) -> dict:
        """Format for frontend display"""
        age = self.resolve_age()

        return {
            'dedup_id': self.dedup_id,
            'name': self.primary_name,
            'age': age,
            'age_note': self.age_note if self.age_conflict else None,
            'city': self.primary_city,
            'state': self.primary_state,
            'sources': self.get_sources(),
            'confidence': round(self.average_confidence, 1),
            'members': [m.to_dict() for m in self.members],
        }


@dataclass
class ScrapeResult:
    """Result from a single broker's scrape"""
    broker: BrokerName
    summaries: List[SummaryResult] = field(default_factory=list)
    status: str = "success"  # success, failed, no_results
    error: Optional[str] = None
    timing_ms: int = 0

    def to_dict(self) -> dict:
        return {
            'broker': self.broker.value,
            'summaries': [s.to_dict() for s in self.summaries],
            'status': self.status,
            'error': self.error,
            'timing_ms': self.timing_ms,
        }


@dataclass
class SequenceOutput:
    """Output from sequence runner"""
    dedup_groups: List[DedupGroup]
    raw_results: Dict[str, ScrapeResult] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON"""
        return {
            'profiles': [g.to_display() for g in self.dedup_groups],
            'raw_results': {k: v.to_dict() for k, v in self.raw_results.items()},
            'metadata': self.metadata,
        }


@dataclass
class QuickScanInput:
    """User input for quickscan"""
    first_name: str
    last_name: str
    city: str
    state: str
