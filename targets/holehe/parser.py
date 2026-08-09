# targets/holehe/parser.py
"""
Holehe Output Parser

Parses output from Holehe email reconnaissance tool.
Holehe returns structured service check results.

Example output:
  [+] twitter.com
  [+] gravatar.com / FullName RockChalkMike / https://gravatar.com/mbertken
  [-] amazon.com
  [x] facebook.com
  [!] github.com
"""

from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class HoleheParser:
    """Parser for Holehe CLI output"""

    # Status indicators from holehe CLI output
    FOUND_MARKER = "[+]"
    NOT_FOUND_MARKER = "[-]"
    RATE_LIMIT_MARKER = "[x]"
    ERROR_MARKER = "[!]"

    def parse_cli_output(self, cli_output: str) -> List[Dict[str, Any]]:
        """
        Parse Holehe CLI output into structured results.

        Holehe prints results like:
        [+] twitter.com
        [+] gravatar.com / FullName RockChalkMike / https://gravatar.com/...
        [-] amazon.com
        [x] facebook.com
        [!] github.com

        Args:
            cli_output: Raw output from holehe CLI

        Returns:
            List of service result dictionaries
        """
        results = []
        lines = cli_output.split('\n')

        for line in lines:
            result = self._parse_line(line)
            if result:
                results.append(result)

        logger.info(f"Parsed {len(results)} service results from holehe output")
        return results

    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single result line.

        Returns:
            Dict with keys: service, status, metadata (or None if not a result line)
        """
        line = line.strip()

        # Skip empty lines and non-result lines
        if not line:
            return None
        if line.startswith('---'):
            return None
        if 'checked' in line.lower():
            return None
        if line.startswith('|'):
            return None
        if any(skip in line for skip in ['Twitter :', 'Github :', 'BTC', '%', '100%', 'Error occurred']):
            return None

        # Determine status based on marker
        status = None
        content = None

        if line.startswith(self.FOUND_MARKER):
            status = 'found'
            content = line[4:].strip()
        elif line.startswith(self.NOT_FOUND_MARKER):
            status = 'not_found'
            content = line[4:].strip()
        elif line.startswith(self.RATE_LIMIT_MARKER):
            status = 'rate_limit'
            content = line[4:].strip()
        elif line.startswith(self.ERROR_MARKER):
            status = 'error'
            content = line[4:].strip()
        else:
            # Not a result line
            return None

        # Parse service name and metadata
        parts = content.split(' / ')
        service = parts[0].strip()

        # Extract metadata if present
        metadata = None
        if len(parts) > 1:
            metadata = self._parse_metadata(parts[1:])

        result = {
            'service': service,
            'status': status,
        }

        if metadata:
            result['metadata'] = metadata

        return result

    def _parse_metadata(self, parts: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse metadata fields from result line.

        Metadata can include:
        - FullName {name}
        - URLs
        - Other profile info

        Returns:
            Dict with parsed metadata, or None if no metadata
        """
        metadata = {}

        for part in parts:
            part = part.strip()

            if not part:
                continue

            # Check for URL
            if part.startswith('http'):
                metadata['profileUrl'] = part
            # Check for FullName pattern
            elif part.startswith('FullName'):
                # Format: "FullName SomeName" or similar
                # Extract everything after "FullName "
                name_part = part.replace('FullName', '').strip()
                if name_part:
                    metadata['name'] = name_part
            # Check for other patterns (could be username, etc.)
            elif part and not part.startswith('['):
                # Generic metadata - store as additional info
                if 'info' not in metadata:
                    metadata['info'] = []
                metadata['info'].append(part)

        return metadata if metadata else None

    def get_summary_stats(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate summary statistics from parsed results.

        Args:
            results: List of parsed service results

        Returns:
            Dict with counts by status
        """
        summary = {
            'totalServicesChecked': len(results),
            'servicesFound': 0,
            'servicesNotFound': 0,
            'rateLimited': 0,
            'errors': 0,
        }

        for result in results:
            status = result.get('status')
            if status == 'found':
                summary['servicesFound'] += 1
            elif status == 'not_found':
                summary['servicesNotFound'] += 1
            elif status == 'rate_limit':
                summary['rateLimited'] += 1
            elif status == 'error':
                summary['errors'] += 1

        return summary

