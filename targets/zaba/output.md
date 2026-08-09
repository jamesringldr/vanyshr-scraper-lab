# Zaba Output Schema

## Output Data Structure

The scraper returns normalized data. Since Zaba has no summary/profile split, all results are complete profiles:

```python
{
    "source": "zaba",
    "search_params": {
        "firstName": "John",
        "lastName": "Smith",
        "city": "Denver",
        "state": "CO"
    },
    "summary_results": [],  # Empty - Zaba doesn't have a summary page
    "profiles": [  # Multiple full profiles returned
        {
            "profileId": "zaba_001",
            "fullName": "John Smith",
            "age": 55,
            "currentAddress": {
                "street": "123 Main Street",
                "city": "Denver",
                "state": "CO",
                "zip": "80202",
                "formatted": "123 Main Street, Denver, CO 80202"
            },
            "phoneNumbers": [
                {
                    "number": "(303) 555-1234",
                    "type": "landline",
                    "status": "current"
                }
            ],
            "emailAddresses": [
                "john.smith@example.com"
            ],
            "relatives": [
                {
                    "name": "Jane Smith",
                    "relationship": "Spouse"
                }
            ],
            "associates": [
                {
                    "name": "Bob Johnson",
                    "relationship": "neighbor"
                }
            ],
            "properties": [
                {
                    "address": "123 Main Street, Denver, CO 80202",
                    "type": "Single Family",
                    "yearBuilt": 1998,
                    "estimatedValue": 425000
                }
            ]
        },
        {
            "profileId": "zaba_002",
            "fullName": "John Smith Jr.",
            ...
        }
    ],
    "timestamp": "2024-08-09T14:30:00Z",
    "execution_time_ms": 3200
}
```

## Output Datapoints Reference

| Datapoint | Source Selector | Type | Normalization | Example |
|-----------|-----------------|------|----------------|---------|
| fullName | `.result-item .name` text | string | Title case, trim | "John Smith" |
| age | `.result-item .age` text | integer | Numeric | 55 |
| street | `.result-item .current-address .street` | string | Proper case | "123 Main Street" |
| city | `.result-item .current-address .city` | string | Proper case | "Denver" |
| state | `.result-item .current-address .state` | string | Uppercase 2-letter | "CO" |
| zip | `.result-item .current-address .zip` | string | 5-digit | "80202" |
| phoneNumber | `.result-item .phone` text | string | (###) ###-#### | "(303) 555-1234" |
| email | `.result-item .email` text | string | Lowercase, trim | "john.smith@example.com" |
| relativeName | `.result-item .relatives .relative .name` | string | Proper case | "Jane Smith" |
| relationship | `.result-item .relatives .relative .rel-type` | string | Title case | "Spouse" |
| propertyAddress | `.result-item .properties .property .address` | string | Full address | "123 Main Street, Denver, CO 80202" |
| propertyType | `.result-item .properties .property .type` | string | Taxonomy | "Single Family" |
| yearBuilt | `.result-item .properties .property .year` | integer | 4-digit | 1998 |

