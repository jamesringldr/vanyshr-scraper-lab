# targets/zaba/parser.py
"""
Zaba HTML Parser

Extracts data from Zaba search page (all results as full profiles on single page).
"""

from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class ZabaParser:
    """Parser for Zaba HTML responses"""

    def parse_profiles_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse Zaba search page with multiple full profiles.

        Args:
            html: HTML content of Zaba search results page

        Returns:
            List of profile dictionaries (all results on single page)
        """
        soup = BeautifulSoup(html, 'html.parser')
        profiles = []

        try:
            # Zaba displays results as individual blocks on single page
            result_items = soup.select('.result-item') or soup.select('.person-result')

            for item in result_items:
                profile = self._extract_profile(item)
                if profile:
                    profiles.append(profile)

        except Exception as e:
            logger.error(f"Error parsing Zaba profiles: {str(e)}")

        return profiles

    def _extract_profile(self, item_element) -> Optional[Dict[str, Any]]:
        """Extract a single profile from result block"""
        try:
            profile = {}
            profile['profileId'] = item_element.get('data-profile-id') or ''
            profile['fullName'] = self._extract_text(item_element, '.name')
            profile['age'] = self._extract_int(item_element, '.age')

            # Address
            profile['currentAddress'] = self._extract_address(item_element)

            # Contact info
            profile['phoneNumbers'] = self._extract_phones(item_element)
            profile['emailAddresses'] = self._extract_emails(item_element)

            # Relations
            profile['relatives'] = self._extract_relatives(item_element)
            profile['associates'] = self._extract_associates(item_element)

            # Properties
            profile['properties'] = self._extract_properties(item_element)

            return profile

        except Exception as e:
            logger.warning(f"Error extracting profile: {str(e)}")
            return None

    def _extract_address(self, element) -> Dict[str, str]:
        """Extract address from result block"""
        address = {}
        addr_el = element.select_one('.current-address')

        if addr_el:
            address['street'] = self._extract_text(addr_el, '.street')
            address['city'] = self._extract_text(addr_el, '.city')
            address['state'] = self._extract_text(addr_el, '.state')
            address['zip'] = self._extract_text(addr_el, '.zip')

            parts = [address.get('street'),
                    f"{address.get('city')}, {address.get('state')} {address.get('zip')}"]
            address['formatted'] = ', '.join(p for p in parts if p)

        return address

    def _extract_phones(self, element) -> List[Dict[str, str]]:
        """Extract phone numbers"""
        phones = []
        phone_els = element.select('.phone')

        for phone_el in phone_els:
            number = self._extract_text(phone_el, '')
            if number:
                phones.append({
                    'number': self._format_phone(number),
                    'type': phone_el.get('data-type', 'unknown'),
                    'status': 'current',
                })

        return phones

    def _extract_emails(self, element) -> List[str]:
        """Extract email addresses"""
        emails = []
        email_els = element.select('.email')

        for email_el in email_els:
            email = self._extract_text(email_el, '')
            if email:
                emails.append(email.lower())

        return emails

    def _extract_relatives(self, element) -> List[Dict[str, str]]:
        """Extract relatives"""
        relatives = []
        rel_els = element.select('.relatives .relative')

        for rel_el in rel_els:
            relatives.append({
                'name': self._extract_text(rel_el, '.name'),
                'relationship': self._extract_text(rel_el, '.rel-type'),
            })

        return relatives

    def _extract_associates(self, element) -> List[Dict[str, str]]:
        """Extract associates"""
        associates = []
        assoc_els = element.select('.associates .associate')

        for assoc_el in assoc_els:
            associates.append({
                'name': self._extract_text(assoc_el, '.name'),
                'relationship': self._extract_text(assoc_el, '.rel-type'),
            })

        return associates

    def _extract_properties(self, element) -> List[Dict[str, Any]]:
        """Extract properties"""
        properties = []
        prop_els = element.select('.properties .property')

        for prop_el in prop_els:
            properties.append({
                'address': self._extract_text(prop_el, '.address'),
                'propertyType': self._extract_text(prop_el, '.type'),
                'yearBuilt': self._extract_int(prop_el, '.year'),
                'estimatedValue': self._extract_int(prop_el, '.value'),
            })

        return properties

    # Utility methods
    def _extract_text(self, element, selector: str) -> str:
        """Extract and clean text"""
        if not selector:
            return element.get_text(strip=True) if element else ""
        el = element.select_one(selector) if hasattr(element, 'select_one') else None
        return el.get_text(strip=True) if el else ""

    def _extract_int(self, element, selector: str) -> Optional[int]:
        """Extract and parse integer"""
        text = self._extract_text(element, selector)
        if text:
            digits = re.sub(r'[^\d]', '', text)
            try:
                return int(digits)
            except ValueError:
                pass
        return None

    def _format_phone(self, number: str) -> str:
        """Format phone number"""
        if not number:
            return ""
        digits = re.sub(r'\D', '', number)
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return number

