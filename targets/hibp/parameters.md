# HIBP Email Breach Lookup Parameters

## Input Parameters
These are the values passed to `scraper.run(params)`:

| Parameter | Type | Required | Example | Notes |
|-----------|------|----------|---------|-------|
| email | string | Yes | "user@example.com" | Email to check for breaches |
| apiKey | string | Yes | "your-api-key" | HIBP API key (from haveibeenpwned.com) |
| includePasswords | boolean | No | false | Include plaintext passwords in results |
| timeout | int | No | 10 | Request timeout in seconds (default: 10) |

## API Endpoint

### Breached Account Search
**Endpoint**: `GET https://haveibeenpwned.com/api/v3/breachedaccount/{email}`

**Headers**:
- `User-Agent: VanyshrApp` (required by HIBP)
- `x-apikey: {apiKey}` (API authentication)

**Query Parameters**:
- `includeUnverified` (optional, boolean): Include unverified breaches
- `truncateResponse` (optional, boolean): Exclude password hash details

**Response Status**:
- 200: Breach(es) found
- 404: Email not found in any breach
- 429: Rate limited (need backoff)
- 401: Unauthorized (invalid API key)

