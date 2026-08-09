# targets/hudson-rock/username/parser.py
"""
Hudson Rock Username Search API Response Parser
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class HudsonRockUsernameParser:
    """Parser for Hudson Rock username search API responses"""

    def parse_api_response(self, data: Any) -> List[Dict[str, Any]]:
        """
        Parse Hudson Rock API response.

        Args:
            data: JSON response data from Hudson Rock API

        Returns:
            List of normalized stealer dictionaries
        """
        stealers = []

        try:
            if not isinstance(data, dict):
                logger.warning("Hudson Rock response is not a dict")
                return stealers

            # Check if request was successful
            if not data.get('success', False):
                error = data.get('error', 'Unknown error')
                logger.info(f"Hudson Rock request failed: {error}")
                return stealers

            # Extract stealer data
            stealer_list = data.get('data', [])

            for stealer_data in stealer_list:
                normalized = self._normalize_stealer(stealer_data)
                if normalized:
                    stealers.append(normalized)

            logger.info(f"Parsed {len(stealers)} stealers from Hudson Rock response")

        except Exception as e:
            logger.error(f"Error parsing Hudson Rock response: {str(e)}")

        return stealers

    def _normalize_stealer(self, stealer_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize a stealer object from Hudson Rock API.

        Args:
            stealer_data: Stealer object from API

        Returns:
            Normalized stealer dict, or None if invalid
        """
        try:
            stealer_id = stealer_data.get('stealer_id')
            if not stealer_id:
                return None

            credentials = stealer_data.get('credentials', [])
            timestamp = stealer_data.get('timestamp')

            normalized = {
                'stealer_id': stealer_id,
                'malware_name': stealer_data.get('malware_name', 'Unknown'),
                'timestamp': timestamp,
                'compromised_count': len(credentials),
                'credentials': credentials,  # Store raw credentials
            }

            return normalized

        except Exception as e:
            logger.warning(f"Error normalizing stealer: {str(e)}")
            return None

