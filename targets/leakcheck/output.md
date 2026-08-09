# LeakCheck Output Schema

## Output Data Structure

The scraper returns a list of breaches where the email was found, directly from LeakCheck API:

```json
{
    "source": "leakcheck",
    "status": "success",
    "search_params": {
        "email": "test@example.com"
    },
    "breaches": [
        {
            "name": "Mathway.com",
            "date": "2020-01-01",
            "source": "LeakCheck",
            "fields_exposed": [
                "name", "email", "password", "phone", "address",
                "city", "state", "zip", "country", "ssn", "dob",
                "username", "first_name", "last_name", "middle_name",
                "company_name", "ip", "ip1", "ip2", "gender",
                "profile_name", "id", "origin"
            ],
            "exposed_field_count": 22,
            "is_verified": true
        },
        {
            "name": "Bookmate.com",
            "date": "2018-07-01",
            "source": "LeakCheck",
            "fields_exposed": [22 field names...],
            "exposed_field_count": 22,
            "is_verified": true
        }
    ],
    "summary": {
        "totalBreaches": 210,
        "isCompromised": true,
        "compromised_records": 0
    },
    "timestamp": "2026-08-09T15:30:47.464580Z",
    "execution_time_ms": 140
}
```

## Output Datapoints Reference

| Datapoint | Source | Type | Normalization | Example |
|-----------|--------|------|----------------|---------|
| name | API sources.name | string | Trim, title case | "Mathway.com" |
| date | API sources.date | date | ISO 8601 (YYYY-MM-DD) | "2020-01-01" |
| source | Constant | string | Always "LeakCheck" | "LeakCheck" |
| fields_exposed | API fields | array | List of exposed data types | ["name", "email", "password", ...] |
| exposed_field_count | Calculated | integer | Count of fields in array | 22 |
| is_verified | Constant | boolean | Always true (LeakCheck data) | true |
| totalBreaches | Counted | integer | Count of breach items | 210 |
| isCompromised | Calculated | boolean | true if breaches > 0 | true |
| compromised_records | Counted | integer | Sum of records (LeakCheck doesn't provide per-breach counts) | 0 (placeholder) |

## Key Features

- **Rich exposure data**: Shows exactly which types of personal data were exposed (22 types)
- **Many breaches**: test@example.com found in 210 breaches (vs ~2 in HIBP)
- **Verified data**: All LeakCheck breaches are verified
- **Fast response**: ~140ms per lookup
- **No authentication**: Works with public API
- **Date format**: Year-Month format from API (e.g., "2020-01") normalized to ISO 8601

