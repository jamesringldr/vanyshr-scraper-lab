# Vanyshr Scraper Lab - Project Journal

**Project**: Modular, production-ready scrapers for vanyshr-mono app
**Goal**: Build pluggable scraper modules that can be integrated into vanyshr-mono for QuickScan and Subscriber monitoring workflows
**Status**: In Progress - Core modules complete, HTML scrapers in refinement phase

---

## Project Overview

This repo is an **isolated development environment** for building, testing, and perfecting web scrapers before integration into the production vanyshr-mono app. All scrapers are designed as self-contained, pluggable Python modules with a standard interface.

### Architecture

```
targets/
├── {target-name}/
│   ├── scraper.py          # Main async scraper module
│   ├── parser.py           # HTML/JSON parsing logic
│   ├── models.py           # Pydantic/dataclass models
│   ├── __init__.py         # Standard interface export
│   ├── journal.md          # Testing notes
│   ├── parameters.md       # Input params & API details
│   ├── output.md           # Output schema
│   ├── schema.md           # Database schema
│   └── response_examples/  # Sample API responses or HTML
```

### Standard Interface

All scrapers expose the same async function:

```python
from targets.{target} import run

result = await run({
    'param1': 'value1',
    'param2': 'value2',
    ...
})
```

Returns standardized `ScrapeOutput` with:
- `source`: target name
- `status`: success/not_found/failed
- `search_params`: input parameters used
- `results`: parsed data (format varies by target)
- `summary`: aggregated stats
- `timestamp`: ISO 8601
- `execution_time_ms`: execution duration

---

## Target Status

### ✅ PRODUCTION READY (Tested & Working)

#### **1. Holehe** - Email Service Reconnaissance
- **Type**: CLI-based tool (installed package)
- **Input**: email
- **Output**: 123 service checks per email
- **Status**: ✅ COMPLETE
  - Parser: Fully implemented
  - Tested: 2 real emails (jaoehring@gmail.com, michael@bertken.com)
  - Response samples: Saved in response_examples/
  - Execution time: ~10-11 seconds
- **Location**: `targets/holehe/`
- **Files**: Complete with IMPLEMENTATION_COMPLETE.md

#### **2. LeakCheck** - Email Breach Database
- **Type**: REST API (no auth required)
- **Input**: email
- **Output**: 200+ breaches per email (superior to HIBP)
- **Status**: ✅ COMPLETE
  - API endpoint: `https://api.hudsonrock.com/json/v3/search-by-login-emails`
  - Tested: test@example.com (210 breaches, 1357 exposures)
  - Response samples: Saved in response_examples/
  - Execution time: ~140ms
  - **Advantage**: No API key, generous rate limits, more breaches found
- **Location**: `targets/leakcheck/`
- **Files**: Complete with IMPLEMENTATION_COMPLETE.md

---

### 📋 SCAFFOLDED & READY FOR REFINEMENT

#### **3. Hudson Rock** - Infostealer Credential Lookup
- **Type**: REST API (requires API key)
- **Rate Limit**: 50 requests per 10 seconds
- **Max Response**: 20 stealers per request
- **Submodules**:
  - `email/`: Search credentials by email
  - `username/`: Search credentials by username
- **Status**: 📋 SCAFFOLDED
  - All files created and documented
  - Ready for API key testing
  - Need: Real API responses to validate parsing
- **Location**: `targets/hudson-rock/`
- **Next**: Test both endpoints, capture real responses, update response_examples/

#### **4. NPD** - National Public Data (Residential)
- **Type**: HTML scraper
- **Pages**: Summary + Full Profile (2 separate pages)
- **Status**: 📋 SCAFFOLDED
  - Full module structure in place
  - Selectors defined in parameters.md
  - Need: Real HTML examples (summary.html + profile.html)
  - Need: Selector validation and testing
  - Need: Parser implementation refinement
- **Location**: `targets/npd/`
- **Next**: Collect real HTML examples, test selectors, implement/refine parsing

#### **5. Anywho** - Residential People Search
- **Type**: HTML scraper
- **Pages**: Summary + Full Profile (2 separate pages)
- **Status**: 📋 SCAFFOLDED
  - Full module structure in place
  - Selectors defined in parameters.md
  - Need: Real HTML examples (summary.html + profile.html)
  - Need: Selector validation and testing
  - Need: Parser implementation refinement
- **Location**: `targets/anywho/`
- **Next**: Collect real HTML examples, test selectors, implement/refine parsing

#### **6. FPS** (FirstPoint Search) - Residential Data
- **Type**: HTML scraper
- **Pages**: Summary + Full Profile (2 separate pages)
- **Status**: 📋 SCAFFOLDED
  - Full module structure in place
  - Selectors defined in parameters.md
  - Need: Real HTML examples (summary.html + profile.html)
  - Need: Selector validation and testing
  - Need: Parser implementation refinement
- **Location**: `targets/fps/`
- **Next**: Collect real HTML examples, test selectors, implement/refine parsing

#### **7. Zaba** - Residential Data (Single Page Results)
- **Type**: HTML scraper
- **Pages**: Single Page (all results as full profiles on one page - no summary/profile split)
- **Status**: 📋 SCAFFOLDED
  - Full module structure in place (special case)
  - Selectors defined in parameters.md
  - Need: Real HTML examples (profile.html with multiple results)
  - Need: Selector validation and testing
  - Need: Parser implementation refinement
- **Location**: `targets/zaba/`
- **Next**: Collect real HTML examples, test selectors, implement/refine parsing

#### **8. HIBP** - Have I Been Pwned (Email Breach Database)
- **Type**: REST API (requires API key)
- **Status**: 📋 SCAFFOLDED (Deprecated in favor of LeakCheck)
  - Kept for reference/backup
  - Stricter rate limits than LeakCheck
  - Not recommended for production use
- **Location**: `targets/hibp/`
- **Decision**: Consider removing when LeakCheck is fully validated

---

## Workflow Overview

### Phase 1: Individual Target Development ✅ (Current)
- ✅ Holehe - Complete
- ✅ LeakCheck - Complete
- 📋 Hudson Rock - In Progress (waiting for API key testing)
- 📋 NPD, Anywho, FPS, Zaba - Starting (need HTML examples)

### Phase 2: Scraper Sequence (Next)
- Build orchestration layer that chains multiple targets
- Create **QuickScan** workflow (limited targets, summary only)
- Create **Subscriber** workflow (all targets, full profiles, monthly monitoring)
- Implement error handling, retry logic, deduplication

### Phase 3: Integration (Final)
- Wire into vanyshr-mono app
- Connect to database schema
- Set up monitoring/alerting
- Deploy to production

---

## For New Agents: Getting Started

### Understanding the Project
1. Read this file (you are here)
2. Check `targets/{target}/journal.md` for specific target status
3. Check `targets/{target}/IMPLEMENTATION_COMPLETE.md` if available

### What Needs to Be Done Now

**Priority 1 - HTML Scrapers (NPD, Anywho, FPS, Zaba)**:
1. Collect real HTML examples from each site
   - Need: Both summary.html and profile.html for NPD, Anywho, FPS
   - Need: Single profile.html with multiple results for Zaba
   - Save to: `targets/{target}/sourceHTML/`
2. Validate CSS selectors defined in `parameters.md`
3. Implement parser.py using BeautifulSoup
4. Test parser against real HTML examples
5. Update output.md with actual field names/formats
6. Update journal.md with testing results

**Priority 2 - Hudson Rock API**:
1. Obtain Hudson Rock API key (with search-by-login permission)
2. Test both email and username endpoints
3. Save real API responses to response_examples/
4. Validate parser against real responses
5. Update journal.md with test results

**Priority 3 - Database Integration** (later phase):
1. Implement database persistence per schema.md
2. Create migration scripts
3. Set up monitoring queries

---

## Testing Protocol

Each target should have:
- ✅ `journal.md` with testing notes
- ✅ `output.md` with actual datapoints (not theoretical)
- ✅ `response_examples/` with 1-3 real examples
- ✅ Working parser that handles real data
- ✅ Schema validation complete

---

## Key Decisions Made

1. **LeakCheck over HIBP**: Better rate limits, no auth, finds more breaches
2. **Modular targets**: Each target is self-contained, pluggable
3. **Standard interface**: All targets use same async `run()` function
4. **Separate HTML from API modules**: Different scrapers, same structure
5. **HTML scrapers have 2 flavors**:
   - Summary + Profile (NPD, Anywho, FPS)
   - Profile only (Zaba - returns multiple full profiles on one page)

---

## Git Workflow

- **Working branch**: `dev/scraper-targets` (currently active)
- **Main branch**: `main` (production, never commit directly)
- **Staging branch**: `staging` (pre-prod validation, if needed)

All work goes through `dev/scraper-targets`. Pull requests go to staging/main.

---

## Files Structure

```
vanyshr-scraper-lab/
├── JOURNAL.md                          # ← YOU ARE HERE
├── targets/
│   ├── holehe/                         # ✅ Complete
│   ├── leakcheck/                      # ✅ Complete
│   ├── hudson-rock/
│   │   ├── email/                      # 📋 Scaffolded
│   │   └── username/                   # 📋 Scaffolded
│   ├── npd/                            # 📋 Scaffolded
│   ├── anywho/                         # 📋 Scaffolded
│   ├── fps/                            # 📋 Scaffolded
│   ├── zaba/                           # 📋 Scaffolded
│   └── hibp/                           # 📋 Scaffolded (deprecated)
└── holehe-email-scrape/                # Lab testing folder (not committed)
```

---

## Contact/Context

- **Project Owner**: James O
- **Repo**: https://github.com/jamesringldr/vanyshr-scraper-lab
- **Target Integration**: vanyshr-mono app (separate repo)
- **Last Updated**: 2026-08-11

---

## Quick Reference

### Running a Scraper Locally

```python
import asyncio
from targets.holehe import run

result = asyncio.run(run({
    'email': 'test@example.com'
}))
print(result)
```

### Testing a Parser

```python
from targets.leakcheck.parser import LeakCheckParser
import json

with open('targets/leakcheck/response_examples/leakcheck_response_example.json') as f:
    data = json.load(f)

parser = LeakCheckParser()
breaches = parser.parse_api_response(data)
print(f"Found {len(breaches)} breaches")
```

### Adding HTML Examples

1. Capture actual HTML from target site
2. Save to `targets/{target}/sourceHTML/`
3. Commit to git (use `git add targets/{target}/sourceHTML/`)
4. Reference in parser tests

---

## Questions?

Refer to individual target journals:
- `targets/holehe/journal.md` - Holehe implementation notes
- `targets/leakcheck/journal.md` - LeakCheck implementation notes
- `targets/{target}/parameters.md` - API/selector details
- `targets/{target}/output.md` - Output schema

Good luck! 🚀
