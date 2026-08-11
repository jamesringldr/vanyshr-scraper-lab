"""
Deduplication engine for sequence runner.
Matches profiles across brokers and scores them.
"""

import logging
from typing import List, Dict, Tuple
from difflib import SequenceMatcher
import hashlib

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

    def calculate_match_score(self, summary1: SummaryResult, summary2: SummaryResult) -> float:
        """
        Calculate match score between two summaries (0-100).

        Thresholds:
          75+: Merge (same person)
          50-75: Group (possible match)
          <50: Separate (different person)
        """
        score = 0.0

        # NAME SIMILARITY (45 points) - PRIMARY
        name_score = self._compare_names(summary1.full_name, summary2.full_name)
        score += name_score * 45.0

        # LOCATION MATCH (35 points) - SECONDARY
        location_score = self._compare_locations(summary1, summary2)
        score += location_score * 35.0

        # AGE COMPATIBILITY (10 points) - CONTEXTUAL ONLY
        age_score = self._compare_ages(summary1.age, summary2.age)
        score += age_score * 10.0

        # BROKER CREDIBILITY (10 points)
        # For now: all brokers equal weight
        score += 10.0

        return min(100.0, score)  # Cap at 100

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

    def _compare_locations(self, summary1: SummaryResult, summary2: SummaryResult) -> float:
        """
        Compare locations (0-1 scale).

        Returns:
          1.0: City + State match
          0.7: State match only
          0.6: One location empty, state matches
          0.5: Both empty (neutral)
          0.4: City match only
          0.0: No match
        """
        city1 = summary1.address.split(',')[0].strip().lower() if summary1.address else ""
        city2 = summary2.address.split(',')[0].strip().lower() if summary2.address else ""

        # Extract state (last part after comma)
        state1 = ""
        if summary1.address and ',' in summary1.address:
            state1 = summary1.address.split(',')[-1].strip().lower()

        state2 = ""
        if summary2.address and ',' in summary2.address:
            state2 = summary2.address.split(',')[-1].strip().lower()

        # Both empty = neutral
        if not city1 and not state1 and not city2 and not state2:
            return 0.5

        # One location empty
        if (not city1 or not city2) and (state1 and state2):
            if state1 == state2:
                return 0.6
            else:
                return 0.0

        # Both present
        if city1 and city2 and state1 and state2:
            city_match = city1 == city2
            state_match = state1 == state2

            if city_match and state_match:
                return 1.0
            elif state_match:
                return 0.7
            elif city_match:
                return 0.4

        # One empty, one full = 0 (not enough info)
        return 0.0

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
