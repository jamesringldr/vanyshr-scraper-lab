# Anywho Output Schema

## Output Data Structure

The scraper returns normalized data in this format:

```python
{
    "source": "anywho",
    "search_params": {
        "firstName": "John",
        "lastName": "Smith",
        "city": "Denver",
        "state": "CO"
    },
    "summary_results": [
        {
            "resultId": "anywho_abc123",
            "fullName": "John Smith",
            "address": "123 Main St, Denver, CO 80202",
            "ageRange": "50-59",
            "location": "Denver, CO",
            "profileUrl": "https://www.anywho.com/..."
        }
    ],
    "profile": {
        "profileId": "anywho_abc123",
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
        "familyMembers": [
            {
                "name": "Jane Smith",
                "relationship": "Spouse",
                "age": 54
            }
        ],
        "properties": [
            {
                "address": "123 Main Street, Denver, CO 80202",
                "type": "Single Family Home",
                "estimatedValue": 425000
            }
        ]
    },
    "timestamp": "2024-08-09T14:30:00Z",
    "execution_time_ms": 2890
}
```

## Output Datapoints Reference

| Datapoint | Source Selector | Type | Normalization | Example |
|-----------|-----------------|------|----------------|---------|
| fullName | `.profile-name h1` text OR `.nameHeading` | string | Title case, trim | "John Smith" |
| age | `.profile-info .dob` text or calculate | integer | Calculate from DOB if needed | 55 |
| ageRange | `.search-result .age-range` text | string | Format as "##-##" | "50-59" |
| street | `.address-section .street` | string | Proper case, trim | "123 Main Street" |
| city | `.address-section .city` | string | Proper case, trim | "Denver" |
| state | `.address-section .state` | string | Uppercase 2-letter | "CO" |
| zip | `.address-section .zip` | string | 5-digit ZIP | "80202" |
| phoneNumber | `.contact-info .phone` text | string | (###) ###-#### format | "(303) 555-1234" |
| phoneType | `.phone-type` attr or inferred | enum | landline/mobile | "landline" |
| email | `.contact-info .email` text | string | Lowercase, trim | "john.smith@example.com" |
| familyName | `.family-member .name` | string | Proper case | "Jane Smith" |
| relationship | `.family-member .relationship` | string | Title case | "Spouse" |
| familyAge | `.family-member .age` | integer | Numeric age | 54 |
| propertyAddress | `.property .address` | string | Full address | "123 Main Street, Denver, CO 80202" |
| propertyType | `.property .type` | string | Standard taxonomy | "Single Family Home" |
| propertyValue | `.property .value` | integer | Numeric estimate | 425000 |

