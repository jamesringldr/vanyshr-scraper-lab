# Hudson Rock Username Search Testing Journal

**Target**: Hudson Rock Username Search
**Type**: Infostealer credential lookup by username
**API Endpoint**: Search by Usernames (POST)
**Permission Required**: search-by-login

## Overview
Hudson Rock Username Search scans infostealer databases for compromised credentials associated with usernames. Returns stealer and credential information.

## Status
- [ ] API response examples collected
- [ ] Scraper implementation complete
- [ ] Parser implementation complete
- [ ] Integration tested with real usernames
- [ ] Database schema validated

## API Details
- **Rate Limit**: 50 requests per 10 seconds
- **Max Response**: 20 stealers
- **Max Response Time**: 90 seconds
- **Authentication**: API key required
- **Response Models**: stealer, credential

## Testing Notes
(to be filled in as development progresses)

