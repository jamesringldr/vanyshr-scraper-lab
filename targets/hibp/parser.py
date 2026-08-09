# targets/hibp/parser.py
"""
HIBP API Response Parser

Parses JSON responses from Have I Been Pwned API.
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class HibpParser:
    """Parser for HIBP API responses"""

    def parse_breaches_response(self, json_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Parse breached account response from HIBP API.

        Args:
            json_data: List of breach objects from HIBP API

        Returns:
            List of normalized breach dictionaries
        """
        breaches = []

        try:
            for breach in json_data:
                normalized = {
                    'breachId': breach.get('Name'),
                    'breachName': breach.get('Title', breach.get('Name')),
                    'breachDate': breach.get('BreachDate'),
                    'addedDate': breach.get('AddedDate'),
                    'modifiedDate': breach.get('ModifiedDate'),
                    'pwnCount': breach.get('PwnCount', 0),
                    'description': breach.get('Description', ''),
                    'dataClasses': breach.get('DataClasses', []),
                    'isVerified': breach.get('IsVerified', False),
                    'isFabricated': breach.get('IsFabricated', False),
                    'isActive': breach.get('IsActive', False),
                    'isRetired': breach.get('IsRetired', False),
                    'isSpamList': breach.get('IsSpamList', False),
                    'logoPath': breach.get('LogoPath', ''),
                }
                breaches.append(normalized)

        except Exception as e:
            logger.error(f"Error parsing breaches response: {str(e)}")

        return breaches

    def parse_pastes_response(self, json_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Parse pastes response from HIBP API.

        Args:
            json_data: List of paste objects from HIBP API

        Returns:
            List of normalized paste dictionaries
        """
        pastes = []

        try:
            for paste in json_data:
                normalized = {
                    'source': paste.get('Source', 'Unknown'),
                    'id': paste.get('Id'),
                    'title': paste.get('Title'),
                    'date': paste.get('Date'),
                    'emailCount': paste.get('EmailCount', 0),
                }
                pastes.append(normalized)

        except Exception as e:
            logger.error(f"Error parsing pastes response: {str(e)}")

        return pastes

