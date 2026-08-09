# targets/fps/parser.py
"""
FPS HTML Parser

Extracts data from FPS summary and profile pages using CSS selectors.
"""

from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class FPSParser:
    """Parser for FPS HTML responses"""

    def parse_summary_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse FPS summary search results page.

        Args:
            html: HTML content of summary results page

        Returns:
            List of summary result dictionaries
        """
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        try:
            result_items = soup.select('.result-row')

            for item in result_items:
                result = self._extract_summary_result(item)
                if result:
                    results.append(result)

        except Exception as e:
            logger.error(f"Error parsing FPS summary: {str(e)}")

        return results

    def parse_profile_html(self, html: str) -> Dict[str, Any]:
        """
        Parse FPS full profile page.

        Args:
            html: HTML content of profile page

        Returns:
            Profile data dictionary
        """
        soup = BeautifulSoup(html, 'html.parser')
        profile = {}

        try:
            # Personal info
            profile['fullName'] = self._extract_text(soup, 'h1.profile-heading') or \
                                 self._extract_text(soup, '.person-name')
            profile['age'] = self._extract_int(soup, '.age-info')

            # Address
            profile['currentAddress'] = self._extract_current_address(soup)
            profile['previousAddresses'] = self._extract_previous_addresses(soup)

            # Contact info
            profile['phoneNumbers'] = self._extract_phones(soup)
            profile['emailAddresses'] = self._extract_emails(soup)

            # Relations
            profile['relatives'] = self._extract_relatives(soup)
            profile['associates'] = self._extract_associates(soup)

            # Properties
            profile['properties'] = self._extract_properties(soup)

        except Exception as e:
            logger.error(f"Error parsing FPS profile: {str(e)}")

        return profile

    def _extract_summary_result(self, item_element) -> Optional[Dict[str, Any]]:
        """Extract a single summary result"""
        try:
            return {
                'resultId': item_element.get('data-result-id') or '',
                'fullName': self._extract_text(item_element, '.name'),
                'address': self._extract_text(item_element, '.address'),
                'age': self._extract_int(item_element, '.age'),
                'phone': self._extract_text(item_element, '.phone'),
                'profileUrl': self._extract_attr(item_element, 'a.view-profile', 'href'),
            }
        except Exception as e:
            logger.warning(f"Error extracting summary result: {str(e)}")
            return None

    def _extract_current_address(self, soup) -> Dict[str, str]:
        """Extract current address"""
        address = {}
        addr_section = soup.select_one('.address-current')

        if addr_section:
            address['street'] = self._extract_text(addr_section, '.street')
            address['city'] = self._extract_text(addr_section, '.city')
            address['state'] = self._extract_text(addr_section, '.state')
            address['zip'] = self._extract_text(addr_section, '.zip')

            # Try formatted address
            formatted = self._extract_text(addr_section, '.full-addr')
            if formatted:
                address['formatted'] = formatted
            else:
                parts = [address.get('street'),
                        f"{address.get('city')}, {address.get('state')} {address.get('zip')}"]
                address['formatted'] = ', '.join(p for p in parts if p)

        return address

    def _extract_previous_addresses(self, soup) -> List[Dict[str, str]]:
        """Extract previous addresses"""
        addresses = []
        addr_items = soup.select('.address-history li')

        for item in addr_items:
            addr = {}
            addr['street'] = self._extract_text(item, '.street')
            addr['city'] = self._extract_text(item, '.city')
            addr['state'] = self._extract_text(item, '.state')
            addr['zip'] = self._extract_text(item, '.zip')

            parts = [addr.get('street'),
                    f"{addr.get('city')}, {addr.get('state')} {addr.get('zip')}"]
            addr['formatted'] = ', '.join(p for p in parts if p)

            addresses.append(addr)

        return addresses

    def _extract_phones(self, soup) -> List[Dict[str, str]]:
        """Extract phone numbers"""
        phones = []
        phone_items = soup.select('.phone-section .phone-number')

        for item in phone_items:
            number = self._extract_text(item, '')
            if number:
                phones.append({
                    'number': self._format_phone(number),
                    'type': item.get('data-type', 'unknown'),
                    'status': 'current',
                })

        return phones

    def _extract_emails(self, soup) -> List[str]:
        """Extract email addresses"""
        emails = []
        email_items = soup.select('.email-section .email')

        for item in email_items:
            email = self._extract_text(item, '')
            if email:
                emails.append(email.lower())

        return emails

    def _extract_relatives(self, soup) -> List[Dict[str, str]]:
        """Extract relatives"""
        relatives = []
        rel_items = soup.select('.relatives-section .relative')

        for item in rel_items:
            relatives.append({
                'name': self._extract_text(item, '.name'),
                'relationship': self._extract_text(item, '.rel-type'),
            })

        return relatives

    def _extract_associates(self, soup) -> List[Dict[str, str]]:
        """Extract known associates"""
        associates = []
        assoc_items = soup.select('.associates-section .associate')

        for item in assoc_items:
            associates.append({
                'name': self._extract_text(item, '.name'),
                'relationship': self._extract_text(item, '.rel-type'),
            })

        return associates

    def _extract_properties(self, soup) -> List[Dict[str, Any]]:
        """Extract properties"""
        properties = []
        prop_items = soup.select('.properties-section .property')

        for item in prop_items:
            properties.append({
                'address': self._extract_text(item, '.address'),
                'propertyType': self._extract_text(item, '.type'),
                'yearBuilt': self._extract_int(item, '.year'),
                'estimatedValue': self._extract_int(item, '.value'),
            })

        return properties

    # Utility methods
    def _extract_text(self, element, selector: str) -> str:
        """Extract and clean text from element"""
        if not selector:
            return element.get_text(strip=True) if element else ""
        el = element.select_one(selector) if hasattr(element, 'select_one') else None
        if el:
            return el.get_text(strip=True)
        return ""

    def _extract_attr(self, element, selector: str, attr: str) -> str:
        """Extract attribute from element"""
        el = element.select_one(selector) if hasattr(element, 'select_one') else None
        if el:
            return el.get(attr, "")
        return ""

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
        """Format phone number to (###) ###-#### format"""
        if not number:
            return ""
        digits = re.sub(r'\D', '', number)
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return number

