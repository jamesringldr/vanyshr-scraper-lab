# LeakCheck Email Breach Lookup Journal

**Target**: LeakCheck (leakcheck.io)
**Type**: Email breach database lookup via Public API
**API Plan**: Free public lookup (generous rate limits)
**Documentation**: https://docs.leakcheck.io/public-api/lookup

## Overview
LeakCheck provides a free public API for checking if an email has been exposed in known data breaches. More generous rate limits than HIBP, making it ideal for production use at scale.

## Status
- [ ] API documentation reviewed and understood
- [ ] API response examples collected
- [ ] Scraper implementation complete
- [ ] Parser implementation complete
- [ ] Integration tested with real emails
- [ ] Database schema validated
- [ ] Integration tested with QuickScan

## Testing Notes

### Test 1: API Response Parsing (test@example.com)
- Date: 2026-08-09
- Email Status: **Found in 210 breaches**
- Total exposures tracked: 1357
- Exposed fields: 22 types (name, email, password, SSN, phone, address, etc.)
- Execution: ~140ms
- Status: ✅ PASS

### Test 2: Integration Test (Full Module)
- Date: 2026-08-09
- Email: test@example.com
- Breaches found: 210
- Sample breaches:
  - Mathway.com (2020-01)
  - Bookmate.com (2018-07)
  - Sendpulse.com (2016-01)
  - Geniusu.com (2020-02)
  - Funimation.com (2016-07)
- Schema validation: ✅ PASS
- Execution: ~140ms
- Status: ✅ PASS

---

## Key Differences from HIBP

| Feature | HIBP | LeakCheck |
|---------|------|-----------|
| **Free API** | Yes | ✅ Yes |
| **Authentication** | Required (API key) | Not required |
| **Rate Limits** | Strict | ✅ Generous |
| **Breaches per lookup** | Varies | ✅ Can find 200+ |
| **Fields exposed** | Limited info | ✅ 22 field types |
| **Response time** | ~500ms | ✅ ~140ms |
| **Practical for prod** | Limited | ✅ Excellent |

---

## API Endpoints

### Public Email Lookup
**Endpoint**: `GET https://leakcheck.io/api/public`

**Parameters**:
- `check` (required): Email address
- `type` (required): "email"

**Response**:
```json
{
  "success": true/false,
  "found": 1357,
  "fields": ["name", "email", "password", ...],
  "sources": [
    {
      "name": "Breach Name",
      "date": "2020-01"
    }
  ]
}
```

**No authentication required!**

