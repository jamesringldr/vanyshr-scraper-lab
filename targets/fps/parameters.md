# FPS (FirstPoint Search) Scraper Parameters

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
**URL Pattern**: `https://fps.com/search?name=[firstName]+[lastName]&location=[city]+[state]`

| Field | Selector | Notes |
|-------|----------|-------|
| Result Count | `.result-count` | Total matches |
| Summary Name | `.result-row .name` | Person name |
| Summary Address | `.result-row .address` | Address preview |
| Summary Age | `.result-row .age` | Age range or age |
| Summary Phone | `.result-row .phone` | Phone if available |
| Result Link | `.result-row a.view-profile` | Link to full profile |

### Full Profile Page
**URL Pattern**: `https://fps.com/profile/...`

| Field | Selector | Notes |
|-------|----------|-------|
| Full Name | `h1.profile-heading` or `.person-name` | Person's full name |
| Age | `.age-info` | Numeric age |
| Current Address | `.address-current` | Primary address |
| Address Formatted | `.address-current .full-addr` | Full formatted address |
| Previous Addresses | `.address-history li` | Past addresses |
| Phone | `.phone-section .phone-number` | Phone number |
| Email | `.email-section .email` | Email address |
| Relatives | `.relatives-section .relative` | Family members |
| Associates | `.associates-section .associate` | Known associates |
| Properties | `.properties-section .property` | Real estate |

