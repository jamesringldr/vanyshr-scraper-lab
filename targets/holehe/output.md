# Holehe Output Schema

## Output Data Structure

The scraper returns a list of services with email status:

```python
{
    "source": "holehe",
    "search_params": {
        "email": "user@example.com",
        "onlyUsed": false,
        "timeout": 10
    },
    "results": [
        {
            "service": "twitter.com",
            "status": "found",  # 'found', 'not_found', 'rate_limit', 'error'
            "email": "user@example.com",
            "metadata": None
        },
        {
            "service": "gravatar.com",
            "status": "found",
            "email": "user@example.com",
            "metadata": {
                "name": "John Smith",
                "profileUrl": "https://gravatar.com/johnsmith",
                "avatar": "https://..."
            }
        },
        {
            "service": "lastpass.com",
            "status": "found",
            "email": "user@example.com",
            "metadata": None
        },
        {
            "service": "facebook.com",
            "status": "rate_limit",
            "email": "user@example.com",
            "metadata": None
        },
        {
            "service": "amazon.com",
            "status": "not_found",
            "email": "user@example.com",
            "metadata": None
        }
    ],
    "summary": {
        "totalServicesChecked": 123,
        "servicesFound": 7,
        "servicesNotFound": 60,
        "rateLimited": 45,
        "errors": 11
    },
    "timestamp": "2024-08-09T14:30:00Z",
    "execution_time_ms": 10290
}
```

## Output Datapoints Reference

| Datapoint | Source | Type | Notes | Example |
|-----------|--------|------|-------|---------|
| service | Module name | string | Service domain/name | "twitter.com" |
| status | Module result | enum | found/not_found/rate_limit/error | "found" |
| email | Input email | string | Email checked | "user@example.com" |
| metadata | Module-specific | object | Additional info if available | {name, profileUrl, ...} |
| metadataName | metadata.name | string | Name from service if available | "John Smith" |
| metadataUrl | metadata.profileUrl | string | Profile URL if available | "https://..." |
| totalServicesChecked | Holehe counter | integer | Total services scanned | 123 |
| servicesFound | Counted result | integer | Where email exists | 7 |
| servicesNotFound | Counted result | integer | Where email doesn't exist | 60 |
| rateLimited | Counted result | integer | Rate-limited services | 45 |
| errors | Counted result | integer | Services with errors | 11 |

