# Zaba Scraper Parameters

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

### Full Profile Page (Single Page, Multiple Results)
**URL Pattern**: `https://search.zaba.com/s?q=[FirstName]+[LastName]&where=[City],+[State]`

| Field | Selector | Notes |
|-------|----------|-------|
| Result Count | `.totalResults` or `.result-count-text` | Total matches found |
| Result Blocks | `.result-item` or `.person-result` | Each result is a full profile |
| Person Name | `.result-item .name` or `.person-name` | Full name of person |
| Age | `.result-item .age` | Age of person |
| Current Address | `.result-item .current-address` | Primary residence |
| Phone | `.result-item .phone` | Phone number |
| Email | `.result-item .email` | Email if available |
| Relatives | `.result-item .relatives .relative` | Family members |
| Associates | `.result-item .associates .associate` | Known associates |
| Properties | `.result-item .properties .property` | Real estate owned |

