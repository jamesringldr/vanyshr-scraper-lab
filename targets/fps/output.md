# FPS Output Schema

## Output Data Structure

The scraper returns normalized data in this format:

```python
{
    "source": "fps",
    "search_params": {
        "firstName": "John",
        "lastName": "Smith",
        "city": "Denver",
        "state": "CO"
    },
    "summary_results": [
        {
            "resultId": "fps_xyz789",
            "fullName": "John Smith",
            "address": "123 Main St, Denver, CO 80202",
            "age": 55,
            "phone": "(303) 555-1234",
            "profileUrl": "https://fps.com/profile/..."
        }
    ],
    "profile": {
        "profileId": "fps_xyz789",
        "fullName": "John Smith",
        "age": 55,
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
                "formatted": "456 Oak Ave, Boulder, CO 80301"
            }
        ],
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
    "timestamp": "2024-08-09T14:30:00Z",
    "execution_time_ms": 2650
}
```

## Output Datapoints Reference

| Datapoint | Source Selector | Type | Normalization | Example |
|-----------|-----------------|------|----------------|---------|
| fullName | `h1.profile-heading` or `.person-name` text | string | Title case, trim | "John Smith" |
| age | `.age-info` text | integer | Numeric or calculated | 55 |
| street | `.address-current .street` | string | Proper case | "123 Main Street" |
| city | `.address-current .city` | string | Proper case | "Denver" |
| state | `.address-current .state` | string | Uppercase 2-letter | "CO" |
| zip | `.address-current .zip` | string | 5-digit | "80202" |
| phoneNumber | `.phone-section .phone-number` text | string | (###) ###-#### | "(303) 555-1234" |
| phoneType | `.phone-section [data-type]` attr | enum | landline/mobile | "landline" |
| email | `.email-section .email` text | string | Lowercase, trim | "john.smith@example.com" |
| relativeName | `.relatives-section .relative .name` | string | Proper case | "Jane Smith" |
| relationship | `.relatives-section .relative .rel-type` | string | Title case | "Spouse" |
| associateName | `.associates-section .associate .name` | string | Proper case | "Bob Johnson" |
| propertyAddress | `.properties-section .property .address` | string | Full address | "123 Main Street, Denver, CO 80202" |
| propertyType | `.properties-section .property .type` | string | Taxonomy | "Single Family" |
| yearBuilt | `.properties-section .property .year` | integer | 4-digit | 1998 |
| estimatedValue | `.properties-section .property .value` | integer | Numeric | 425000 |

