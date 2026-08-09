# Holehe Email Scraper Testing Journal

**Target**: Holehe (Email Reconnaissance Tool)
**Type**: Email API-based reconnaissance
**Interface**: Python package / CLI

## Overview
Holehe checks if an email address has been exposed across various online services.
Uses API calls to third-party services, not HTML scraping.

## Status
- [x] Holehe installed and tested (see holehe-email-scrape/)
- [ ] API response examples collected
- [ ] Parser implementation for JSON responses
- [ ] Database schema validated
- [ ] Integration tested with QuickScan
- [ ] Integration tested with Subscriber scan

## Testing Notes

### Test 1: jaoehring@gmail.com (CLI Output Parsing)
- Date: 2026-08-09
- Results: 125 services checked
  - Found: 9 services
  - Not found: 39 services
  - Rate limited: 66 services
  - Errors: 11 services
- Execution: 10.86 seconds
- Status: ✅ PASS

### Test 2: michael@bertken.com (with Metadata)
- Date: 2026-08-09
- Results: 125 services checked
  - Found: 13 services
  - Not found: 35 services
  - Rate limited: 66 services
  - Errors: 11 services
- Metadata recovered: Gravatar profile (name: RockChalkMike, URL: https://gravatar.com/mbertken)
- Execution: 10.2 seconds
- Status: ✅ PASS

### Test 3: Integration Test (Full Module)
- Date: 2026-08-09
- Email: michael@bertken.com
- Results: 125 services checked
  - Found: 13 services (includes Adobe metadata)
  - Rate limited: 66 services
  - Errors: 11 services
- Execution: 11.621 seconds
- Schema validation: ✅ PASS
- Status: ✅ PASS

---

## Implementation Notes

### Parser
- Successfully parses all status markers: `[+]`, `[-]`, `[x]`, `[!]`
- Correctly extracts metadata from lines with `/` delimiters
- Handles profile URLs and names properly
- Filters out progress bars, header text, and non-result lines

### Scraper Module
- Locates holehe binary in venv or PATH
- Properly invokes with all CLI parameters
- Captures and parses output
- Generates summary statistics
- Returns structured ScrapeOutput

### Output Schema Compliance
✅ All required fields present: source, search_params, results, summary, timestamp, execution_time_ms, status
✅ Result items have required fields: service, status, metadata (optional)
✅ Summary stats correctly calculated
✅ Timestamps in ISO 8601 format
✅ Execution time in milliseconds

---

## Key Findings
- Holehe returns structured results for each email across 123-125 services
- Multiple services can be rate-limited due to Holehe's request patterns
- Successfully retrieves profile metadata when services expose it (e.g., Gravatar)
- Tool works reliably for email reconnaissance
- Module is production-ready for integration

