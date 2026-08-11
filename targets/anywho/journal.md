# AnyWho Scraper Testing Journal

**Target**: AnyWho (anywho.com)
**Type**: Residential data broker
**Pages**: Summary + Full Profile
**Status**: ✅ COMPLETE — Ready for integration testing

## Overview
AnyWho provides people search with summary results and detailed profile pages.
Implementation uses context.dev Extract API with two-step extraction (listing→profile).

## Implementation Status (2026-08-11)

### ✅ Completed
- [x] Scraper module built using context.dev Extract API
- [x] URL building: `/people/{first}+{last}/{state-name}/{city}`
- [x] Schema definition for summary and profile extraction
- [x] Summary result extraction and model mapping
- [x] Profile data extraction and model mapping
- [x] Age parsing with DOB support
- [x] Error handling with graceful fallback
- [x] Unit tests: 3/3 passing
- [x] Live integration tests: 3/3 passing

## Unit Test Results (2026-08-11)

### Test Coverage: 3/3 Passing ✅
1. **URL Building** — Correct AnyWho format with state name mapping
2. **Summary Extraction** — Multiple results from listing page
3. **Profile Extraction** — Full profile data with arrays

## Live Testing Results (2026-08-11)

### 3/3 Tests Passed ✅

**Test Queries:**
1. James Oehring, Cameron, MO — 40,753ms, 2 summaries ✅
2. John Smith, New York, NY — 30,563ms, 20 summaries ✅
3. Mary Johnson, Los Angeles, CA — 23,723ms, 14 summaries ✅

**Performance:**
- Success Rate: 100% (3/3)
- Avg Latency: ~31.6 seconds
- Data Quality: Multiple results with full names

**Key Findings:**
- AnyWho returns many results (2-20 per query)
- URL format critical: lowercase + join, full state name with hyphens
- Graceful fallback when profile pages block (uses listing data)
- Works reliably with context.dev Extract API

## URL Format

**Pattern**: `/people/{first}+{last}/{state-name}/{city}`
- Lowercase all parts
- First/Last: joined with `+`
- State: full name (e.g., "missouri", "new-york")
- City: hyphens for spaces (e.g., "los-angeles")

**Example**: `/people/james+oehring/missouri/cameron`

## Architecture

**Two-Step Extraction:**
1. **Listing page**: Extract summary results (all matches)
2. **Profile page** (first result): Extract detailed profile (name, age, phone, email, family, properties)
3. **Fallback**: If profile extraction fails, use listing data

## Key Differences from FPS/NPD

- **Multiple results**: AnyWho returns 2-20 results, not just 1 match
- **Summary-first**: We have multiple summaries to choose from
- **Profile fallback**: Gracefully handles when detailed profile page blocks
- **Latency**: ~30-40s (similar to NPD)

## Next Steps

1. ✅ Unit Testing — COMPLETE (3/3 tests passed)
2. ✅ Live Testing — COMPLETE (3/3 tests passed)
3. Integration — Ready for app integration
4. Optimization — Monitor performance at scale

## Conclusion

AnyWho scraper is **production-ready** with context.dev Extract API.
The scraper reliably extracts multiple results and handles graceful fallback to listing data when profile details are unavailable.

