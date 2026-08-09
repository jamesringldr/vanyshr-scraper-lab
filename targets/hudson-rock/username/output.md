# Hudson Rock Username Search Output Schema

## Output Data Structure

```json
{
  "source": "hudson-rock-username",
  "status": "success",
  "search_params": {
    "username": "john_doe"
  },
  "breaches": [
    {
      "stealer_id": "stealer_uuid_123",
      "malware_name": "Lumma",
      "timestamp": "2024-01-15T10:30:00Z",
      "compromised_count": 2,
      "credentials": [
        {
          "url": "https://example.com/login",
          "login": "john_doe",
          "password": "password123",
          "user_agent": "Mozilla/5.0..."
        },
        {
          "url": "https://github.com/login",
          "login": "john_doe",
          "password": "secure_pass",
          "user_agent": "Mozilla/5.0..."
        }
      ]
    }
  ],
  "summary": {
    "total_stealers": 3,
    "total_credentials": 5,
    "malware_types": ["Lumma", "Raccoon"],
    "is_compromised": true
  },
  "timestamp": "2024-08-09T14:30:00Z",
  "execution_time_ms": 520
}
```

## Output Datapoints Reference

| Datapoint | Source | Type | Notes | Example |
|-----------|--------|------|-------|---------|
| stealer_id | API | string | Unique stealer identifier | "uuid_123" |
| malware_name | API | string | Type of malware | "Lumma", "Raccoon", "Vidar" |
| timestamp | API | datetime | When credentials were stolen | "2024-01-15T10:30:00Z" |
| url | API credential | string | Target website URL | "https://example.com/login" |
| login | API credential | string | Compromised username | "john_doe" |
| password | API credential | string | Compromised password | "password123" |
| user_agent | API credential | string | Browser user agent | "Mozilla/5.0..." |
| total_stealers | Counted | integer | Number of stealer events | 3 |
| total_credentials | Counted | integer | Total credentials found | 5 |
| malware_types | Extracted | array | Unique malware names | ["Lumma", "Raccoon"] |
| is_compromised | Calculated | boolean | Username found in any breach | true |

