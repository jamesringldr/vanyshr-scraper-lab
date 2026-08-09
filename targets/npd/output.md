# NPD Output Schema

## Output Data Structure

The scraper returns normalized data in this format:

```python
{
    "source": "npd",
    "search_params": {
        "firstName": "John",
        "lastName": "Smith",
        "city": "Denver",
        "state": "CO"
    },
    "summary_results": [
        {
            "resultId": "npd_12345",
            "fullName": "John Smith",
            "addressPreview": "123 Main St, Denver, CO 80202",
            "phonePreview": "(303) 555-1234",
            "matchScore": 95,
            "profileUrl": "https://www.nationalpublicdata.com/report/..."
        }
    ],
    "profile": {
        "profileId": "npd_12345",
        "fullName": "John Alexander Smith",
        "dateOfBirth": "1985-06-15",
        "age": 40,
        "currentAddress": {
            "street": "123 Main Street",
            "city": "Denver",
            "state": "CO",
            "zip": "80202",
            "formatted": "123 Main Street, Denver, CO 80202"
        },
        "previousAddresses": [
            {
                "street": "456 Oak Ave",
                "city": "Boulder",
                "state": "CO",
                "zip": "80301",
                "formatted": "456 Oak Ave, Boulder, CO 80301",
                "yearsActive": "2010-2015"
            }
        ],
        "phoneNumbers": [
            {
                "number": "(303) 555-1234",
                "type": "mobile",
                "status": "current"
            }
        ],
        "emailAddresses": [
            "john.smith@example.com"
        ],
        "relatives": [
            {
                "name": "Jane Smith",
                "relationship": "Spouse",
                "address": "123 Main Street, Denver, CO 80202"
            }
        ],
        "properties": [
            {
                "address": "123 Main Street, Denver, CO 80202",
                "type": "Single Family",
                "yearBuilt": 1998,
                "estimated_value": 425000
            }
        ]
    },
    "timestamp": "2024-08-09T14:30:00Z",
    "execution_time_ms": 3450
}
```

## Output Datapoints Reference

| Datapoint | Source Selector | Type | Normalization | Example |
|-----------|-----------------|------|----------------|---------|
| fullName | `h1.report-title` text | string | Title case, trim | "John Alexander Smith" |
| dateOfBirth | `.dob-section .value` attr/text | date | ISO 8601 (YYYY-MM-DD) | "1985-06-15" |
| age | Calculated from DOB | integer | Math.floor(now - dob) | 40 |
| street | `.address-current .street` | string | Proper case, trim | "123 Main Street" |
| city | `.address-current .city` | string | Proper case, trim | "Denver" |
| state | `.address-current .state` | string | Uppercase 2-letter | "CO" |
| zip | `.address-current .zip` | string | 5-digit ZIP | "80202" |
| phoneNumber | `.phone-item` text | string | (###) ###-#### format | "(303) 555-1234" |
| phoneType | `.phone-item [data-type]` attr | enum | mobile/landline/voip | "mobile" |
| email | `.email-item` text | string | Lowercase, trim | "john.smith@example.com" |
| relativeName | `.relative-card .name` | string | Proper case | "Jane Smith" |
| relationship | `.relative-card .rel-type` | string | Enum value | "Spouse" |
| propertyType | `.property-item .type` | string | Standard taxonomy | "Single Family" |
| yearBuilt | `.property-item .year-built` | integer | 4-digit year | 1998 |

