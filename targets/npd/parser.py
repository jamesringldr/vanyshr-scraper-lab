# targets/npd/parser.py
"""
NPD HTML Parser

Extracts data from NPD summary and profile pages using CSS selectors.
"""

from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class NPDParser:
    """Parser for NPD HTML responses"""

    def parse_summary_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse NPD summary search results page.

        Args:
            html: HTML content of summary results page

        Returns:
            List of summary result dictionaries
        """
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        try:
            result_items = soup.select('.result-item')

            for item in result_items:
                result = self._extract_summary_result(item)
                if result:
                    results.append(result)

        except Exception as e:
            logger.error(f"Error parsing NPD summary: {str(e)}")

        return results

    def parse_profile_html(self, html: str) -> Dict[str, Any]:
        """
        Parse NPD full profile page.

        Args:
            html: HTML content of profile page

        Returns:
            Profile data dictionary
        """
        soup = BeautifulSoup(html, 'html.parser')
        profile = {}

        try:
            # Personal info
            profile['fullName'] = self._extract_text(soup, 'h1.report-title')
            profile['dateOfBirth'] = self._extract_dob(soup)
            profile['age'] = self._extract_age(profile.get('dateOfBirth'))

            # Current address
            profile['currentAddress'] = self._extract_current_address(soup)

            # Previous addresses
            profile['previousAddresses'] = self._extract_previous_addresses(soup)

            # Contact info
            profile['phoneNumbers'] = self._extract_phones(soup)
            profile['emailAddresses'] = self._extract_emails(soup)

            # Relatives
            profile['relatives'] = self._extract_relatives(soup)

            # Properties
            profile['properties'] = self._extract_properties(soup)

        except Exception as e:
            logger.error(f"Error parsing NPD profile: {str(e)}")

        return profile

    def _extract_summary_result(self, item_element) -> Optional[Dict[str, Any]]:
        """Extract a single summary result"""
        try:
            return {
                'resultId': item_element.get('data-result-id'),
                'fullName': self._extract_text(item_element, '.person-name'),
                'addressPreview': self._extract_text(item_element, '.address-preview'),
                'phonePreview': self._extract_text(item_element, '.phone-preview'),
                'matchScore': self._extract_int(item_element, '.match-percentage'),
                'profileUrl': self._extract_attr(item_element, 'a.profile-link', 'href'),
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

            # Build formatted address
            parts = [address.get('street'),
                    f"{address.get('city')}, {address.get('state')} {address.get('zip')}"]
            address['formatted'] = ', '.join(p for p in parts if p)

        return address

    def _extract_previous_addresses(self, soup) -> List[Dict[str, Any]]:
        """Extract previous address history"""
        addresses = []
        addr_items = soup.select('.address-history .addr-row')

        for item in addr_items:
            addr = {
                'street': self._extract_text(item, '.street'),
                'city': self._extract_text(item, '.city'),
                'state': self._extract_text(item, '.state'),
                'zip': self._extract_text(item, '.zip'),
                'yearsActive': self._extract_text(item, '.years-active'),
            }
            # Build formatted
            parts = [addr.get('street'),
                    f"{addr.get('city')}, {addr.get('state')} {addr.get('zip')}"]
            addr['formatted'] = ', '.join(p for p in parts if p)

            addresses.append(addr)

        return addresses

    def _extract_phones(self, soup) -> List[Dict[str, str]]:
        """Extract phone numbers"""
        phones = []
        phone_items = soup.select('.phone-section .phone-item')

        for item in phone_items:
            phones.append({
                'number': self._format_phone(self._extract_text(item, '.number')),
                'type': item.get('data-type', 'unknown'),
                'status': item.get('data-status', 'unknown'),
            })

        return phones

    def _extract_emails(self, soup) -> List[str]:
        """Extract email addresses"""
        emails = []
        email_items = soup.select('.email-section .email-item')

        for item in email_items:
            email = self._extract_text(item, '.email')
            if email:
                emails.append(email.lower())

        return emails

    def _extract_relatives(self, soup) -> List[Dict[str, str]]:
        """Extract relatives"""
        relatives = []
        rel_cards = soup.select('.relatives-section .relative-card')

        for card in rel_cards:
            relatives.append({
                'name': self._extract_text(card, '.name'),
                'relationship': self._extract_text(card, '.rel-type'),
                'address': self._extract_text(card, '.address'),
            })

        return relatives

    def _extract_properties(self, soup) -> List[Dict[str, Any]]:
        """Extract properties"""
        properties = []
        prop_items = soup.select('.property-section .property-item')

        for item in prop_items:
            properties.append({
                'address': self._extract_text(item, '.address'),
                'type': self._extract_text(item, '.type'),
                'yearBuilt': self._extract_int(item, '.year-built'),
                'estimatedValue': self._extract_int(item, '.estimated-value'),
            })

        return properties

    def _extract_dob(self, soup) -> Optional[str]:
        """Extract and format date of birth as ISO 8601"""
        dob_text = self._extract_text(soup, '.dob-section .value')
        if dob_text:
            # Try to parse various formats
            for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%B %d, %Y']:
                try:
                    dt = datetime.strptime(dob_text, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
        return None

    def _extract_age(self, dob: Optional[str]) -> Optional[int]:
        """Calculate age from DOB"""
        if not dob:
            return None
        try:
            birth = datetime.strptime(dob, '%Y-%m-%d')
            today = datetime.today()
            return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        except:
            return None

    # Utility methods
    def _extract_text(self, element, selector: str) -> str:
        """Extract and clean text from element"""
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
            # Remove non-numeric characters except decimal
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

