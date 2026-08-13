"""
Deduplication engine for sequence runner.
Matches profiles across brokers and scores them.
"""

import logging
import re
from typing import List, Dict, Tuple
from difflib import SequenceMatcher
import hashlib

from address_parse import parse_address
from data_models import (
    SummaryResult, DedupGroup, DedupMember, ScrapeResult, BrokerName
)

logger = logging.getLogger(__name__)


class DedupEngine:
    """Deduplication and scoring engine"""

    # Scoring thresholds
    MERGE_THRESHOLD = 75  # Merge if score >= this
    GROUP_THRESHOLD = 50  # Group if score >= this (possible match)

    def deduplicate(
        self,
        scrape_results: Dict[str, ScrapeResult]
    ) -> List[DedupGroup]:
        """
        Deduplicate summaries from multiple brokers.

        Args:
            scrape_results: Dict of broker name -> ScrapeResult

        Returns:
            List of DedupGroup sorted by confidence
        """
        # Flatten all summaries (handle Zaba multi-results)
        all_summaries = self._flatten_summaries(scrape_results)

        logger.info(f"Deduplicating {len(all_summaries)} summaries")

        groups: List[DedupGroup] = []

        # Process each summary
        for summary in all_summaries:
            matched = False

            # Try to match against existing groups
            for group in groups:
                max_score = 0

                # Score against all members of the group
                for member in group.members:
                    score = self.calculate_match_score(
                        summary, member.summary
                    )
                    max_score = max(max_score, score)

                # Add to group if score high enough
                if max_score >= self.MERGE_THRESHOLD:
                    group.add_member(summary, max_score)
                    matched = True
                    logger.debug(
                        f"Merged {summary.broker} result into "
                        f"group {group.dedup_id} (score: {max_score})"
                    )
                    break
                elif max_score >= self.GROUP_THRESHOLD:
                    group.add_member(summary, max_score)
                    matched = True
                    logger.debug(
                        f"Added {summary.broker} to possible match group "
                        f"{group.dedup_id} (score: {max_score})"
                    )
                    break

            # Create new group if no match
            if not matched:
                dedup_id = self._generate_dedup_id(summary)
                group = DedupGroup(dedup_id)
                group.add_member(summary, 100.0)  # First member = 100% confidence
                groups.append(group)
                logger.debug(f"Created new group {dedup_id}")

        # Post-process groups for age conflicts
        for group in groups:
            self._check_age_conflict(group)

        # Sort groups by confidence (highest first)
        groups.sort(key=lambda g: g.average_confidence, reverse=True)

        logger.info(f"Deduplication complete: {len(groups)} groups")

        return groups

    # Weights, summing to 100. Ordered by how much each signal actually
    # distinguishes one person from another in observed broker data.
    W_PHONE     = 30.0   # a shared number is the single strongest link
    W_LOCATION  = 25.0   # current or former address
    W_RELATIVES = 20.0   # "James Oehring + Rickilinda" is far more specific than either alone
    W_NAME      = 20.0
    W_AGE       =  5.0   # contextual only; brokers disagree wildly

    # Ceiling applied when first names are incompatible. Below GROUP_THRESHOLD,
    # so a gated pair is never even offered as a possible match.
    NAME_GATE_CEILING = 45.0

    def calculate_match_score(self, summary1: SummaryResult, summary2: SummaryResult) -> float:
        """
        Score how likely two summaries describe the same person (0-100).

          75+   merge
          50-75 possible match
          <50   separate

        Weighting follows what was observed across the four brokers for one
        person: the same phone appeared in all four, the same relative appeared
        in all four, and the same street address appeared in three plus the
        fourth's address history. Age appeared as 61, 62, 37 and 37 for that
        same person, which is why it is worth 5 points and cannot block a match.

        Name acts as a gate rather than a large weight. Address and phone are
        the strongest signals precisely because they are shared within a
        household, so weighting them heavily without a gate merges spouses:
        James and Rickilinda Oehring share 413 Lovers Ln and the landline
        (816) 632-2218.
        """
        name_score = self._compare_names(summary1.full_name, summary2.full_name)
        location_score = self._compare_locations(summary1, summary2)
        phone_score = self._compare_phones(summary1.phone, summary2.phone)
        relative_score = self._compare_relatives(summary1.relatives, summary2.relatives)
        age_score = self._compare_ages(summary1.age, summary2.age)

        score = (
            phone_score * self.W_PHONE
            + location_score * self.W_LOCATION
            + relative_score * self.W_RELATIVES
            + name_score * self.W_NAME
            + age_score * self.W_AGE
        )

        # No unconditional bonus. Every pair used to receive a flat +10 for
        # "broker credibility", which pushed strangers toward the threshold for
        # free and made a genuine zero impossible.

        if not self._first_names_compatible(summary1.full_name, summary2.full_name):
            return min(score, self.NAME_GATE_CEILING)

        return min(100.0, score)

    @staticmethod
    def _normalize_phones(raw: str) -> set:
        """Digits only, so (816) 632-2218 and 8166322218 compare equal."""
        numbers = set()
        for part in (raw or "").split(','):
            digits = re.sub(r'\D', '', part)
            if len(digits) == 11 and digits.startswith('1'):
                digits = digits[1:]
            if len(digits) == 10:
                numbers.add(digits)
        return numbers

    def _compare_phones(self, phones1: str, phones2: str) -> float:
        """
        Overlap between two phone lists, 0-1.

        Absence is not evidence: FPS publishes no phone on its summary page at
        all, so a missing list returns neutral rather than penalising the pair.
        """
        set1, set2 = self._normalize_phones(phones1), self._normalize_phones(phones2)
        if not set1 or not set2:
            return 0.0
        return len(set1 & set2) / min(len(set1), len(set2))

    @staticmethod
    def _relative_keys(raw: str) -> set:
        """
        Reduce relative names to first+last, dropping middle names and initials.

        Brokers write the same person as "Rickilinda Oehring" and
        "Rickilinda R Oehring".
        """
        keys = set()
        for part in re.split(r'[,;]', raw or ""):
            words = [w for w in re.sub(r'[^A-Za-z ]', ' ', part).lower().split() if len(w) > 1]
            if len(words) >= 2:
                keys.add(f"{words[0]} {words[-1]}")
            elif words:
                keys.add(words[0])
        return {k for k in keys if 'more' not in k}

    def _compare_relatives(self, relatives1: str, relatives2: str) -> float:
        """Overlap between two relative lists, 0-1."""
        set1, set2 = self._relative_keys(relatives1), self._relative_keys(relatives2)
        if not set1 or not set2:
            return 0.0
        return len(set1 & set2) / min(len(set1), len(set2))

    # Short forms that are not prefixes of the full name, so cannot be caught
    # by the prefix rule in _first_names_compatible.
    NICKNAMES = {
        'bob': 'robert', 'rob': 'robert', 'bobby': 'robert',
        'bill': 'william', 'billy': 'william', 'will': 'william',
        'jim': 'james', 'jimmy': 'james', 'jack': 'john',
        'dick': 'richard', 'rick': 'richard', 'peggy': 'margaret',
        'betty': 'elizabeth', 'liz': 'elizabeth', 'beth': 'elizabeth',
        'hank': 'henry', 'ted': 'theodore', 'tony': 'anthony',
        'kate': 'katherine', 'katie': 'katherine', 'nancy': 'ann',
    }

    @staticmethod
    def _parse_address(raw):
        """Delegate to the shared parser; see address_parse.parse_address."""
        return parse_address(raw)

    @classmethod
    def _first_names_compatible(cls, name1: str, name2: str) -> bool:
        """
        Whether two names could belong to the same person.

        This gates the match rather than contributing to it. Household members
        share an address and a landline -- the strongest two signals available --
        so without a name gate a weighted score merges spouses. James and
        Rickilinda Oehring score 0.50 on full-name similarity, because the
        surname carries it.
        """
        first1 = (name1 or "").lower().split()[:1]
        first2 = (name2 or "").lower().split()[:1]
        if not first1 or not first2:
            return True  # nothing to contradict

        a, b = first1[0].strip('.'), first2[0].strip('.')
        if a == b:
            return True

        # Initial against a full name: "j" and "james"
        if len(a) == 1 or len(b) == 1:
            return a[0] == b[0]

        # Short forms: "chris"/"christopher", "deb"/"deborah"
        if len(a) >= 3 and (b.startswith(a) or a.startswith(b)):
            return True

        # Short forms that are not prefixes
        if cls.NICKNAMES.get(a) == b or cls.NICKNAMES.get(b) == a:
            return True
        if cls.NICKNAMES.get(a) and cls.NICKNAMES.get(a) == cls.NICKNAMES.get(b):
            return True

        # A single typo
        return cls._levenshtein_distance(a, b) <= 1

    def _compare_names(self, name1: str, name2: str) -> float:
        """
        Compare two names (0-1 scale).

        Returns:
          1.0: Exact match
          0.95: First + Last match
          0.85: Typo/Levenshtein close
          0.70: First name + last initial
          0.0: No match
        """
        if not name1 or not name2:
            return 0.5  # Neutral

        name1_lower = name1.lower().strip()
        name2_lower = name2.lower().strip()

        # Exact match
        if name1_lower == name2_lower:
            return 1.0

        # Split names
        parts1 = name1_lower.split()
        parts2 = name2_lower.split()

        if len(parts1) < 2 or len(parts2) < 2:
            return 0.3  # Need at least first + last

        # First + Last match
        if parts1[0] == parts2[0] and parts1[-1] == parts2[-1]:
            return 0.95

        # Levenshtein distance < 2 (typos)
        if self._levenshtein_distance(name1_lower, name2_lower) < 2:
            return 0.85

        # First name + last initial match
        if parts1[0] == parts2[0] and parts1[-1][0] == parts2[-1][0]:
            return 0.70

        # Use sequence matcher for partial matches
        ratio = SequenceMatcher(None, name1_lower, name2_lower).ratio()
        if ratio > 0.8:
            return 0.75
        elif ratio > 0.6:
            return 0.50

        return 0.0

    def _addresses_of(self, summary: SummaryResult):
        """Every address a record carries: current first, then any history."""
        out = [self._parse_address(summary.address)]
        for part in re.split(r';', getattr(summary, 'previous_addresses', '') or ''):
            if part.strip():
                out.append(self._parse_address(part))
        return [a for a in out if a["city"] or a["state"] or a["street"]]

    def _score_address_pair(self, a, b) -> float:
        """Similarity of two parsed addresses, 0-1."""
        if a["street"] and a["street"] == b["street"] and a["city"] == b["city"]:
            return 1.0
        if a["postal"] and a["postal"] == b["postal"]:
            return 0.9
        if a["city"] and a["city"] == b["city"] and a["state"] == b["state"]:
            return 0.85
        if a["state"] and a["state"] == b["state"]:
            return 0.35
        return 0.0

    def _compare_locations(self, summary1: SummaryResult, summary2: SummaryResult) -> float:
        """
        Best match across both records' addresses, current and former, 0-1.

        History matters because brokers disagree about which address is
        current. AnyWho lists James Oehring at a Kansas City address while the
        other three list Cameron -- but 413 Lovers Ln sits in AnyWho's
        "Used to live in" section, and that is the only location signal linking
        the records. Comparing current-to-current alone would miss it.

        A former address matching scores slightly below a current one: people
        move, and a shared former address is weaker evidence than a shared
        current one.
        """
        list1, list2 = self._addresses_of(summary1), self._addresses_of(summary2)
        if not list1 or not list2:
            return 0.0

        best = 0.0
        for i, a in enumerate(list1):
            for j, b in enumerate(list2):
                score = self._score_address_pair(a, b)
                if i or j:  # at least one side is a former address
                    score *= 0.9
                best = max(best, score)
        return best

    def _compare_ages(self, age1: int | None, age2: int | None) -> float:
        """
        Compare ages (0-1 scale).

        Note: Age is contextual, not blocking.

        Returns:
          1.0: Exact match or both missing
          0.9: Age difference 1 year
          0.5: Age difference 1-3 years (data varies)
          0.2: Age difference > 3 years (flag for user)
        """
        # Both missing = neutral (good)
        if age1 is None and age2 is None:
            return 1.0

        # One missing = don't penalize
        if age1 is None or age2 is None:
            return 0.8

        # Both present
        diff = abs(age1 - age2)
        if diff == 0:
            return 1.0
        elif diff == 1:
            return 0.9
        elif diff <= 3:
            return 0.5  # Data might vary by 1-3 years
        else:
            return 0.2  # Age differs significantly (flag for user)

    def _check_age_conflict(self, group: DedupGroup):
        """Check if group has age conflicts and set flags"""
        ages = [m.summary.age for m in group.members if m.summary.age]

        if not ages:
            group.age_conflict = False
            group.age_note = None
            return

        min_age = min(ages)
        max_age = max(ages)
        age_diff = max_age - min_age

        if age_diff > 3:
            group.age_conflict = True
            # Create note
            age_counts = {}
            for age in ages:
                age_counts[age] = age_counts.get(age, 0) + 1

            most_common_age = max(age_counts, key=age_counts.get)
            most_common_count = age_counts[most_common_age]

            group.age_note = (
                f"Ages vary across sources: "
                f"{most_common_count}/{len(group.members)} sources show {most_common_age}, "
                f"range {min_age}-{max_age}"
            )
        else:
            group.age_conflict = False
            group.age_note = None

    def _flatten_summaries(self, scrape_results: Dict[str, ScrapeResult]) -> List[SummaryResult]:
        """
        Flatten summaries from all brokers.
        Handles Zaba returning multiple results.
        """
        flattened = []

        for broker_name, result in scrape_results.items():
            flattened.extend(result.summaries)

        logger.debug(f"Flattened {len(flattened)} summaries from {len(scrape_results)} brokers")

        return flattened

    def _generate_dedup_id(self, summary: SummaryResult) -> str:
        """Generate unique ID for a dedup group"""
        # Create ID from name, city, state
        id_parts = [
            summary.full_name.lower().replace(' ', '_'),
            summary.address.split(',')[0].strip().lower().replace(' ', '_') if summary.address else "unknown",
        ]

        id_string = "_".join(id_parts)

        # Hash for uniqueness
        hash_suffix = hashlib.md5(id_string.encode()).hexdigest()[:8]

        return f"{id_string}_{hash_suffix}"

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return DedupEngine._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # j+1 instead of j since previous_row and current_row are one character longer than s2
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
