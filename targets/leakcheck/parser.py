# targets/leakcheck/parser.py
"""
LeakCheck API Response Parser

Parses JSON responses from LeakCheck public API.

LeakCheck API Response Format:
{
    "success": true/false,
    "found": 1357,  # Number of exposures found
    "fields": [...],  # Fields exposed (email, password, etc.)
    "sources": [
        {
            "name": "Breach Name",
            "date": "2020-01"
        },
        ...
    ]
}
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LeakCheckParser:
    """Parser for LeakCheck API responses"""

    def parse_api_response(self, data: Any) -> List[Dict[str, Any]]:
        """
        Parse LeakCheck API response.

        LeakCheck returns:
        - success: boolean indicating if email was found
        - found: count of exposures
        - fields: list of data fields exposed
        - sources: array of breaches with name and date

        Args:
            data: JSON response data from LeakCheck API

        Returns:
            List of normalized breach dictionaries
        """
        breaches = []

        try:
            if not isinstance(data, dict):
                logger.warning("LeakCheck response is not a dict")
                return breaches

            # Check if request was successful
            if not data.get('success', False):
                error = data.get('error', 'Unknown error')
                logger.info(f"LeakCheck request failed: {error}")
                return breaches

            # Extract sources (breaches)
            sources = data.get('sources', [])
            fields = data.get('fields', [])

            for source in sources:
                normalized = self._normalize_breach(source, fields)
                if normalized:
                    breaches.append(normalized)

            logger.info(f"Parsed {len(breaches)} breaches from LeakCheck response")

        except Exception as e:
            logger.error(f"Error parsing LeakCheck response: {str(e)}")

        return breaches

    def _normalize_breach(self, source: Dict[str, Any], fields: List[str]) -> Optional[Dict[str, Any]]:
        """
        Normalize a breach/source object from LeakCheck API.

        Args:
            source: Source object from API (name, date)
            fields: List of exposed field types

        Returns:
            Normalized breach dict, or None if invalid
        """
        try:
            name = source.get('name')
            date = source.get('date')

            if not name:
                return None

            # Parse date format (e.g., "2020-01" or "2020-01-15")
            parsed_date = self._parse_date(date) if date else None

            normalized = {
                'name': name,
                'date': parsed_date,
                'source': source.get('source', 'LeakCheck'),
                'fields_exposed': fields,  # List of what was exposed
                'exposed_field_count': len(fields),
                'is_verified': True,  # LeakCheck data is verified
            }

            return normalized

        except Exception as e:
            logger.warning(f"Error normalizing breach: {str(e)}")
            return None

    @staticmethod
    def _parse_date(date_str: str) -> str:
        """
        Parse date string from LeakCheck format.

        Input formats: "2020-01", "2020-01-15", etc.
        Output format: ISO 8601 "YYYY-MM-DD" (using 01 if month/day not specified)
        """
        try:
            if not date_str:
                return None

            # Split by dash
            parts = date_str.split('-')

            if len(parts) >= 2:
                year = parts[0]
                month = parts[1].zfill(2)  # Pad to 2 digits
                day = parts[2].zfill(2) if len(parts) > 2 else '01'
                return f"{year}-{month}-{day}"
            elif len(parts) == 1:
                # Just year
                return f"{parts[0]}-01-01"

            return None

        except Exception:
            return None

