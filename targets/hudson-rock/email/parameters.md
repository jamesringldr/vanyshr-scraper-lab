# Hudson Rock Email Search Parameters

## Input Parameters

| Parameter | Type | Required | Example | Notes |
|-----------|------|----------|---------|-------|
| email | string | Yes | "user@example.com" | Email to search for |
| apiKey | string | Yes | "your-api-key" | Hudson Rock API key |
| timeout | int | No | 30 | Request timeout in seconds (default: 30) |

## API Endpoint

**Base URL**: `https://api.hudsonrock.com/json/v3`
**Endpoint**: `/search-by-login-emails`
**Method**: POST
**Authentication**: API Key header
**Permission**: search-by-login

### Request Format

```bash
curl -X POST 'https://api.hudsonrock.com/json/v3/search-by-login-emails' \
  -H 'api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "user@example.com"
  }'
```

### Request Parameters

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| email | string | Yes | Email address to search |
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
          "login": "user@example.com",
          "password": "password123",
          "user_agent": "Mozilla/5.0..."
        }
      ]
    }
  ],
  "total": 5
}
```

## Rate Limits
- **50 requests per 10 seconds**
- **Maximum response time: 90 seconds**
- **Maximum response size: 20 stealers**

