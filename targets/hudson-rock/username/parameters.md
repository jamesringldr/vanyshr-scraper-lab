# Hudson Rock Username Search Parameters

## Input Parameters

| Parameter | Type | Required | Example | Notes |
|-----------|------|----------|---------|-------|
| username | string | Yes | "john_doe" | Username to search for |
| apiKey | string | Yes | "your-api-key" | Hudson Rock API key |
| timeout | int | No | 30 | Request timeout in seconds (default: 30) |

## API Endpoint

**Base URL**: `https://api.hudsonrock.com/json/v3`
**Endpoint**: `/search-by-login-usernames`
**Method**: POST
**Authentication**: API Key header
**Permission**: search-by-login

### Request Format

```bash
curl -X POST 'https://api.hudsonrock.com/json/v3/search-by-login-usernames' \
  -H 'api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "john_doe"
  }'
```

### Request Parameters

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| username | string | Yes | Username to search |
| page | integer | No | Page number (default: 1) |
| limit | integer | No | Results per page (default: 20, max: 20) |

## Response Format

Returns array of stealer objects with compromised credentials.

```json
{
  "success": true,
  "data": [
    {
      "stealer_id": "stealer_uuid",
      "malware_name": "Lumma",
      "timestamp": "2024-01-15T10:30:00Z",
      "credentials": [
        {
          "url": "https://example.com/login",
          "login": "john_doe",
          "password": "password123",
          "user_agent": "Mozilla/5.0..."
        }
      ]
    }
  ],
  "total": 3
}
```

## Response Fields
- `success`: Boolean - indicates if lookup was successful
- `data`: Array - list of stealer objects
- `total`: Integer - total number of stealers found

## Rate Limits
- **50 requests per 10 seconds**
- **Maximum response time: 90 seconds**
- **Maximum response size: 20 stealers**

