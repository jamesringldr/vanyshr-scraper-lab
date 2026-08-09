# LeakCheck Email Breach Lookup Parameters

## Input Parameters
These are the values passed to `scraper.run(params)`:

| Parameter | Type | Required | Example | Notes |
|-----------|------|----------|---------|-------|
| email | string | Yes | "user@example.com" | Email to check for breaches |
| timeout | int | No | 15 | Request timeout in seconds (default: 10) |

## API Information

### Public Lookup Endpoint
**Base URL**: `https://leakcheck.io/api/public`
**Plan**: Free public lookup (no API key required)
**Rate Limits**: Very generous - suitable for production at scale
**Authentication**: None required

### Request Format
```
GET https://leakcheck.io/api/public?check=user@example.com&type=email
```

**Query Parameters**:
- `check` (required): Email address to look up
- `type` (required): "email" (for email lookups)

**Headers**:
- `User-Agent`: Should identify your application (e.g., "VanyshrApp/1.0")

### Response Format
```json
{
  "success": true,
  "found": 1357,
  "fields": [
    "name", "email", "password", "phone", "address", 
    "city", "state", "zip", "country", "ssn", "dob",
    "username", "first_name", "last_name", "middle_name",
    "company_name", "ip", "ip1", "ip2", "gender", 
    "profile_name", "id", "origin"
  ],
  "sources": [
    {
      "name": "Mathway.com",
      "date": "2020-01"
    },
    {
      "name": "Bookmate.com",
      "date": "2018-07"
    }
  ]
}
```

### Response Fields
- `success`: Boolean - indicates if lookup was successful
- `found`: Integer - total number of times email appears in breaches
- `fields`: Array - list of data types that were exposed (22 types total)
- `sources`: Array - list of breaches with name and date

### Status Codes
- `200`: Success (check `success` field in response)
- `404`: Not found
- `429`: Rate limited (unlikely with LeakCheck's generous limits)
- `500`: Server error

