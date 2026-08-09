# NPD Scraper Parameters

## Input Parameters
These are the values passed to `scraper.run(params)`:

| Parameter | Type | Required | Example | Notes |
|-----------|------|----------|---------|-------|
| firstName | string | Yes | "John" | First name of target |
| lastName | string | Yes | "Smith" | Last name of target |
| city | string | Yes | "Denver" | City of target |
| state | string | Yes | "CO" | State abbreviation |
| timeout | int | No | 10 | Request timeout in seconds (default: 10) |

## Page-Specific Selectors

### Summary Page
**URL Pattern**: `https://www.nationalpublicdata.com/search?name=...&city=...&state=...`

| Field | Selector | Notes |
|-------|----------|-------|
| Result Count | `.results-count` | Total number of matches |
| Summary Name | `.result-item .person-name` | Person name in result row |
| Summary Address | `.result-item .address-preview` | Brief address preview |
| Summary Phone | `.result-item .phone-preview` | Phone if visible in summary |
| Summary Match Score | `.result-item .match-percentage` | % match confidence |

### Full Profile Page
**URL Pattern**: `https://www.nationalpublicdata.com/report/...`

| Field | Selector | Notes |
|-------|----------|-------|
| Full Name | `h1.report-title` | Full legal name |
| Age/DOB | `.dob-section .value` | Date of birth or calculated age |
| Current Address | `.address-current .full-address` | Primary residence |
| Previous Addresses | `.address-history .addr-row` | Multiple past addresses |
| Phone Numbers | `.phone-section .phone-item` | All associated numbers |
| Email Addresses | `.email-section .email-item` | All known emails |
| Relatives | `.relatives-section .relative-card` | Family member names |
| Properties | `.property-section .property-item` | Real estate owned |

