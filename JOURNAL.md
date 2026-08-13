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

---

## 2026-08-12: Phase 1 Summary Scraper Test Framework Session

### Session Goal
Create comprehensive 17-person test framework to validate Phase 1 summary scrapers (FPS, NPD, AnyWho) and identify most reliable brokers for different data types (age, address, phones, emails, aliases, relatives).

### What Was Built

#### 1. **Data Models Extended**
- Extended `SummaryResult` dataclass across all brokers to include:
  - `phone`: str
  - `email`: str  
  - `aliases`: str (comma/bullet-separated list)
  - `relatives`: str (comma/bullet-separated list)
- Files: `data_models.py` + `/targets/{fps,npd,anywho}/models.py`

#### 2. **HTML Scrapers Implemented**
- **FPS HTML Scraper** (`fps_html_scraper.py`): Extracts summary results with phone/email fields
- **NPD HTML Scraper** (`npd_html_scraper.py`): 
  - Fixed BASE_URL (removed www.)
  - URL format: `/people/{letter}/{first}-{last}/{state-abbr-lower}/{city-lower}/`
  - Uses context.dev HTML method (~$0.001/request)
- **AnyWho HTML Scraper** (`anywho_html_scraper.py`):
  - h3-section based extraction (Lives in, Phone numbers, AKA, May be related to)
  - Reconstructs data-content (Cloudflare blurred data) from HTML attributes
  - Smart spacing: only adds space before letters, not punctuation
  - Phone regex: `\(\d{3}\)\s*\d{3}-\d+`
  - Email regex: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})?`

#### 3. **Test Framework** (`test_all_17_profiles.py`)
- Runs Phase 1 for 17 known people across 3 brokers
- Generates CSV with:
  - **SUMMARY rows**: Per-profile metadata (timing, total results, broker count)
  - **DETAIL rows**: Per-result extracted data (age, address, phones, emails, aliases, relatives)
- Output: `/Users/jameso/Downloads/Test_Profiles_-_detailed_results.csv`

#### 4. **Sequence Runner Updates**
- Updated `_scrape_broker()` method to extract and pass new fields
- Handles broker-specific field name variants (phone vs phonePreview)
- Converts broker results → SummaryResult with all data fields

### Test Results (17-person run)
✅ **Test completed successfully**
- 17 profiles tested across FPS, NPD, AnyWho
- ~50 API requests total, ~52 seconds runtime
- **FPS:** Excellent — 1-5 matches per profile consistently
- **NPD:** 404s expected — users not in database with city/state filter
- **AnyWho:** Good results — extracting detailed data

### Data Extraction Status

| Field | FPS | NPD | AnyWho | Status |
|-------|-----|-----|--------|--------|
| Age | ✅ | ✅ (ageRange) | ✅ | Working |
| Address | ✅ | ✅ | ✅ | Working |
| Phone | ⚠️ | ⚠️ | ⚠️ | Extracted but truncated in CSV |
| Email | ⚠️ | ✅ | ✅ | Working in scrapers |
| Aliases | ✅ | ✅ | ✅ | Working |
| Relatives | ✅ | ✅ | ✅ | Working |

### Known Issues / Blockers

#### ✅ **RESOLVED: was mis-filed as a "CSV parsing problem" — it was extraction**

The earlier entry here blamed the CSV writer. That was wrong, and it sent the
handoff in the wrong direction. `test_all_17_profiles.py` writes exactly what
it is handed: it opens `'w'`, calls `writeheader()` once, and uses `DictWriter`
correctly. The data was already damaged before it reached the CSV.

The giveaway was that truncation was *systematic*: every AnyWho phone lost
exactly its last four digits. A CSV bug does not clip the same four characters
every time.

**Three separate defects, all in extraction:**

1. **AnyWho `_reconstruct_with_data_content()` was not recursive.** AnyWho blurs
   sensitive values — the visible text holds the leading fragment and the rest
   lives in a `data-content` attribute on an *empty* nested span, rendered by
   CSS `before:content-[attr(data-content)]`. The helper's comment said
   "recursively process nested elements" but the code called
   `child.get_text(strip=True)`, which returns visible text only and discards
   every nested `data-content`. The blurred span sits two levels deep
   (`div > span > span[data-content]`), so it was always dropped.
   This damaged phones, email local parts, and street numbers simultaneously.

2. **AnyWho age was never extracted.** The lookup used
   `find('span', string=re.compile(r'Age'))`, but the age span also contains an
   `<svg>`; bs4's `string=` matcher only matches single-child tags, so it never
   hit. Now read from the reconstructed header text.

3. **NPD ignored its own JSON-LD.** NPD is the richest Phase 1 source, but the
   rendered card carries only name, age and city/state. Phones, emails, street
   address and relatives are published solely in the embedded JSON-LD `Person`
   block, which the summary path never read (`_extract_jsonld_person` existed
   but was only used on the profile path).

**Also fixed:** FPS was returning `Cameron, MO` as the address because it read
the link text; the full street address is in the anchor's `title` attribute
(`413 Lovers Ln, Cameron MO 64429`). FPS relatives were present as links under
`<h4>Relatives:</h4>` and simply not parsed.

**Verified — 17-profile re-run, 104 rows:** 0 truncated phones, 0 truncated
emails, AnyWho age 28/28 (was 0/28), NPD contact fields 4/4 (was 0/4),
FPS full street addresses 38/40.

**Why no test caught this:** the existing suite covers the old `workers/`
modules (`npd_scraper`, `anywho_test`) — nothing imported any
`*_html_scraper.py`, which is what the pipeline actually runs. The "46/46
passed, phone reassembly from data-content ✅" result was green on code the
pipeline does not call.

**Regression cover added** (`tests/`, fixture-driven, no network):
- `test_anywho_html_scraper.py`, `test_fps_html_scraper.py`,
  `test_npd_html_scraper.py` — assert *completeness*, not presence
- `test_scrape_broker_contract.py` — the three brokers expose three different
  `SummaryResult` shapes bridged by a getattr chain in `sequence_runner.py`;
  this asserts no populated field silently becomes `""` on the way to the DB
- `data_quality.py` — shared completeness assertions
- `capture_fixtures.py` — re-capture real broker HTML when markup changes

#### ⚠️ **Minor: Zaba Residential Connection Errors**
- [Errno 61] Connection refused on serv01:8789
- Expected behavior — service not running
- Does not affect Phase 1 summary scrapers (FPS, NPD, AnyWho)

### Files Modified/Created This Session

**Data Models:**
- `data_models.py` — Updated SummaryResult dataclass
- `/targets/fps/models.py` — Added phone, email, aliases, relatives fields
- `/targets/npd/models.py` — Added ageRange, email, aliases, relatives fields  
- `/targets/anywho/models.py` — Added phone, email, aliases, relatives fields

**Scrapers:**
- `fps_html_scraper.py` — New
- `npd_html_scraper.py` — Complete rewrite with HTML method
- `anywho_html_scraper.py` — Complete rewrite with h3-section parsing

**Test/Sequence:**
- `test_all_17_profiles.py` — New 17-person test framework
- `sequence_runner.py` — Updated `_scrape_broker()` method (~line 270)

**Test Data:**
- `/Users/jameso/Downloads/Test_Profiles_-_detailed_results.csv` — Results (with parsing issues)

### Next Steps

1. **NPD coverage** — 13 of 17 profiles return NO_RESULTS. Extraction is now
   confirmed correct (the 4 that do return are 100% populated), so this is
   either genuine database coverage or the city/state URL filter being too
   strict. Worth testing the same names without the city segment before
   concluding NPD is simply thin.

2. **AnyWho match quality** — separate from extraction: for `oehring` AnyWho
   returns "James A Oehring", age 37, at a Kansas City address, whose AKA is
   "James Allen Oehring Jr." That is likely the son, not the 61/62-year-old in
   Cameron that FPS and NPD return. Dedup should not silently merge them.

3. **Phase 1 field coverage is now broker-specific** — FPS summary genuinely
   carries no phone or email (they exist only on the full profile page); NPD
   carries everything; AnyWho carries everything but not for every record.
   Consolidation should prefer NPD for contact data.

4. **Repo layout** — the lab is no longer a repo nested inside its own
   worktree; `vanyshr-scraper-sequence` is now the single working tree.

### Handoff Documentation

Created comprehensive handoff package in Vanyshr-mono:
- **Location:** `/Vanyshr-mono/packages/scraper-lab-phase1/`
- **README.md** — File structure, what works/breaks, next steps
- **HANDOFF_PROMPT.md** — Detailed debug guide with 4 hypotheses and step-by-step fixes
- **sample_results.csv** — Example showing the parsing issue
- All working files copied to mono repo

---

## Where the scraper-to-database mapping lives

The field-by-field mapping of what each scraper produces to where it is stored
is **not in this repo**. It lives with the schema it describes:

    vanyshr-mono  docs/scraper-data-flow.md   (branch dev/pilot-scan-db)

It is a schema document in substance -- destination columns, constraints, and
which fields are queryable versus buried in JSONB -- and sits next to
`schema.md`, which describes the tables themselves.

**It goes stale from changes made here.** Its producing-side tables were
generated from `data_models.py` and `targets/*/models.py`, so adding or
renaming a scraper field will not show up in any diff over there. The
regeneration command is at the top of that document; run it when the field
inventory moves.

---

## Deferred: broker quality analysis, to run with risk calibration

When the full-profile sweep exists (profiles + LeakCheck + Holehe, with the
correct person selected per broker), that same dataset answers a second
question beyond risk-score calibration: **which brokers are actually worth
running, and for what.**

Do both analyses off one sweep. The scores and the broker comparison need the
same inputs, and running the sweep twice costs real money.

### 1. Per data type — is the data any good

For each data type, across all brokers:

- **fill rate** — how often is it present at all
- **completeness** — truncated values, missing components (a phone without its
  last four, an email with a one-character local part, an address without a
  house number). The assertions in `tests/data_quality.py` already encode what
  "complete" means; reuse them as measures rather than pass/fail
- **validity** — plausible on its face (well-formed phone, resolvable domain)
- **agreement** — when two brokers report the same field for the same person,
  do they match? Age is the known offender: 61 / 62 / 37 / 37 for one person.
  Worth knowing whether phones and addresses agree as reliably as they appeared
  to on a single record

### 2. Per broker — holistically

- **recall** — of the test profiles, how many did this broker find at all.
  Known so far from a 5-profile Phase 1 sweep: Zaba missed 1, AnyWho 2, NPD 4
- **precision** — of the results returned, how many are the right person. Needs
  the labelled expected-profile set, which is a prerequisite for Phase 2
  testing anyway
- **richness** — average number of populated data types per person
- **uniqueness** — what does this broker provide that no other does. Zaba is
  the only source of phone line type, carrier, county and coordinates; NPD
  returned the most emails; AnyWho the deepest address history
- **cost per useful record** — calls made against records that turned out to be
  the right person

### 3. Data type by broker — the cross-tab

The one that actually drives sequencing decisions: **which broker to trust for
which field.** A table of broker × data type, scored on fill rate and
completeness, e.g. best source of phone numbers, of emails, of relatives, of
address history.

This feeds three things directly:
- consolidation precedence — whose value wins when brokers disagree
- fallback logic — if the best source for a field misses, who is second
- whether a broker earns its call at all, or only for one or two fields

### Prerequisites

1. `run_summary_test.py` writes incrementally and bounds its timeout — **done**
2. `expected_profile_url` (or the broker's stable id) added to the test CSV, so
   Phase 2 fetches the right person rather than a stranger
3. A sweep covering full profiles, LeakCheck and Holehe, not just Phase 1

---
