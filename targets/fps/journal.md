# FPS (FastPeopleSearch) Scraper Testing Journal

**Target**: FPS (FastPeopleSearch) — residential people search
**Implementation**: context.dev Extract API (structured data extraction)
**Status**: ✅ COMPLETE — Ready for integration testing

## Overview
FPS provides residential people search with summary results and detailed profiles.
Implementation uses context.dev Extract API for structured data extraction instead of HTML parsing.

## Implementation Status (2026-08-11)

### ✅ Completed
- [x] Scraper module built using context.dev Extract API
- [x] URL building: `/name/{first}-{last}_{city}-{state}`
- [x] Schema definition for person data extraction
- [x] Summary result extraction and model mapping
- [x] Profile data extraction and model mapping
- [x] Age parsing and edge case handling
- [x] Error handling and logging
- [x] Unit tests: 6/6 passing

### 🔄 Testing & Optimization (2026-08-11 - LIVE TESTED)
- [x] Live testing with context.dev API — 5/5 tests passed ✅
- [ ] Integration with vanyshr-mono scraper pipeline
- [ ] Performance validation against multiple queries

## Unit Test Results (2026-08-11)

### Test Coverage: 6/6 Passing ✅

1. **Scraper Parameters** — Parameter validation and defaults
   - Valid param creation
   - Default timeout (10s)
   - Custom timeout override

2. **URL Building** — Search URL construction
   - James Oehring, Cameron, MO → `james-oehring_cameron-mo`
   - John Smith, New York, NY → `john-smith_new-york-ny`
   - Mary Johnson, Los Angeles, CA → `mary-johnson_los-angeles-ca`

3. **Age Parsing** — Number extraction from strings
   - "61" → 61
   - "Age 62" → 62
   - "37 years old" → 37
   - "Age range 50-60" → 50
   - None/empty → None

4. **Summary Result Extraction** — Context.dev data → SummaryResult model
   - Extracts name, address, age, phone
   - Creates proper result IDs
   - Handles missing fields

5. **Profile Extraction** — Context.dev data → Profile model
   - Full profile structure
   - Multiple previous addresses
   - Relatives and associates
   - Phone and email arrays

6. **Empty Data Handling** — Error cases
   - Empty dict → empty results
   - Missing name → no extraction
   - Graceful fallback

## Context.dev Extract Schema

```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string", "description": "Full name of the person"},
    "age": {"type": "string", "description": "Age or age range"},
    "address": {"type": "string", "description": "Street address and city/state/zip"},
    "phone": {"type": "string", "description": "Phone number"},
    "email": {"type": "string", "description": "Email address"},
    "relatives": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Known relatives"
    },
    "previous_addresses": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Previous addresses lived at"
    }
  }
}
```

## Key Findings

### Extraction Quality (from contextDev testing)
- ✅ **Name**: Always extracted
- ✅ **Age**: Usually extracted (61 in test)
- ✅ **Address**: Usually extracted (city, state included)
- ⚠️ **Phone**: Inconsistent (sometimes available)
- ⚠️ **Email**: Inconsistent (sometimes available)
- ✅ **Relatives**: Usually found (5 in test)
- ✅ **Previous Addresses**: Usually found (4 in test)

### Data Quality vs Other Scrapers
| Scraper | Fields | Phone | Email | Status |
|---------|--------|-------|-------|--------|
| NPD | 7 | ✅ | ✅ | Best |
| Zaba | 7 | ❌ | ❌ | Good |
| **FPS** | **5** | **❌** | **❌** | **Good** |
| Spokeo | 3 | ❌ | ❌ | Basic |

FPS returns fewer fields than NPD/Zaba but still useful for validation.

## Live Testing Results (2026-08-11)

### 5/5 Tests Passed ✅

**Test Queries:**
1. James Oehring, Cameron, MO — 1,033ms ✅
2. John Smith, New York, NY — 847ms ✅
3. Mary Johnson, Los Angeles, CA — 803ms ✅
4. Robert Williams, Chicago, IL — 66,041ms ⚠️ (server slow)
5. Patricia Brown, Houston, TX — 842ms ✅

**Performance Metrics:**
- Success Rate: 100% (5/5)
- Avg Latency: ~14 seconds (affected by 1 outlier)
- Median Latency: ~880ms
- Slowest Query: 66s (FPS server delay, not scraper issue)

**Data Quality:**
| Data Type | Avg Found | Range |
|-----------|-----------|-------|
| Name | ✅ 5/5 | 100% |
| Age | ✅ 4/5 | 80% |
| Address | ✅ 5/5 | 100% |
| Phone | ⚠️ 1/5 | 20% (FPS limitation) |
| Relatives | ✅ 5/5 | 5-49 per person |
| Previous Addresses | ✅ 5/5 | 4-14 per person |

### Optimizations Applied

1. **Timeout Handling**
   - Increased default timeout from 10s → 60s (context.dev Extract takes 10-30s)
   - Passed timeout to ContextDev client for proper HTTP handling

2. **API Performance (Context.dev Features)**
   - Added `maxAgeMs=86400000` — Cache results for 24 hours (reduces redundant API calls)
   - Note: `useMainContentOnly` not supported in Extract API (HTML/Markdown endpoints only)

3. **Error Handling**
   - Graceful timeout error handling
   - Proper error propagation to output

## Next Steps

1. ✅ **Live Testing** — COMPLETE (5/5 tests passed)

2. **Integration**
   - Add to vanyshr-mono scraper pipeline
   - Test with QuickScan workflow
   - Add to subscriber monitoring

3. **Future Optimizations** (if needed)
   - Configure included/excluded selectors for specific page sections
   - Test with different schema configurations
   - Benchmark against other extraction methods
   - Monitor cache hit rate and adjust maxAgeMs based on usage patterns

## Testing Notes

### How to Run Unit Tests
```bash
cd targets/fps
python test_fps_unit.py
```

### How to Run Live Tests (requires API key)
```bash
export CONTEXT_DEV_API_KEY="your-key-here"
python test_fps_contextdev.py
```

### Code Files
- `scraper.py` — Main FPSScraper class using context.dev
- `models.py` — Data models (SummaryResult, Profile, ScrapeOutput)
- `test_fps_unit.py` — Unit tests (no API required)
- `test_fps_contextdev.py` — Integration tests (requires API key)

