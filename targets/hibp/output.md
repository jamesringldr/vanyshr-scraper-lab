# HIBP Output Schema

## Output Data Structure

The scraper returns a list of breaches where the email was found:

```python
{
    "source": "hibp",
    "search_params": {
        "email": "user@example.com"
    },
    "breaches": [
        {
            "breachId": "Equifax",
            "breachName": "Equifax",
            "breachDate": "2017-09-07",
            "addedDate": "2017-10-01T23:56:24Z",
            "modifiedDate": "2018-02-04T21:48:35Z",
            "pwnCount": 147013025,
            "description": "In mid-2017, Equifax, one of the largest credit reporting agencies...",
            "dataClasses": [
                "Email addresses",
                "Passwords",
                "Personal details",
                "Social Security numbers"
            ],
            "isVerified": true,
            "isFabricated": false,
            "isActive": true,
            "isRetired": false,
            "isSpamList": false,
            "logoPath": "https://haveibeenpwned.com/images/affiliatelogo/equifax.png"
        },
        {
            "breachId": "LinkedIn",
            "breachName": "LinkedIn",
            "breachDate": "2012-05-05",
            ...
        }
    ],
    "pastes": [
        {
            "source": "Pastebin",
            "id": "abc123def456",
            "title": "Leaked LinkedIn Database",
            "date": "2012-05-06T00:00:00Z",
            "emailCount": 500000
        }
    ],
    "summary": {
        "totalBreaches": 2,
        "totalPastes": 1,
        "compressedRecordCount": 147013027,
        "isCompromised": true
    },
    "timestamp": "2024-08-09T14:30:00Z",
    "execution_time_ms": 450
}
```

## Output Datapoints Reference

| Datapoint | Source | Type | Notes | Example |
|-----------|--------|------|-------|---------|
| breachName | HIBP API | string | Name of breach | "Equifax" |
| breachDate | HIBP API | date | When breach occurred | "2017-09-07" |
| pwnCount | HIBP API | integer | Total records in breach | 147013025 |
| description | HIBP API | string | Breach description | "In mid-2017, Equifax..." |
| dataClasses | HIBP API | array | Types of data exposed | ["Email", "Password", ...] |
| isVerified | HIBP API | boolean | Verified by HIBP | true |
| source | HIBP API | string | Paste source | "Pastebin" |
| pasteId | HIBP API | string | Paste ID | "abc123def456" |
| totalBreaches | Counted | integer | Total breaches found | 2 |
| totalPastes | Counted | integer | Total pastes found | 1 |
| isCompromised | Calculated | boolean | Email in any breach | true |

