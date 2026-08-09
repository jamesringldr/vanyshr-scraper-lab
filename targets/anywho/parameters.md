# Anywho Scraper Parameters

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
**URL Pattern**: `https://www.anywho.com/search/name/[firstName]+[lastName]/[City]+[State]`

| Field | Selector | Notes |
|-------|----------|-------|
| Result Count | `.results-info .count` | Total number of matches |
| Summary Name | `.search-result .name` | Person name in result row |
| Summary Address | `.search-result .address` | Address preview |
| Summary Age | `.search-result .age-range` | Age range bracket |
| Summary Match Link | `.search-result a.result-link` | Link to full profile |
| Result Location | `.search-result .location` | City, State from result |

### Full Profile Page
**URL Pattern**: `https://www.anywho.com/...` (varies)

| Field | Selector | Notes |
|-------|----------|-------|
| Full Name | `.profile-name h1` or `.nameHeading` | Person's full name |
| Age/DOB | `.profile-info .dob` or `.ageInfo` | Age or date of birth |
| Current Address | `.address-section .current-addr` | Primary residence address |
| Address Formatted | `.address-section .addr-complete` | Full formatted address |
| Phone | `.contact-info .phone` | Phone number if available |
| Email | `.contact-info .email` | Email if available |
| Family Members | `.family-section .family-member` | Relatives listed |
| Properties | `.property-section .property` | Real estate owned |
| Neighbors | `.neighbors-section .neighbor` | Nearby residents (optional) |

