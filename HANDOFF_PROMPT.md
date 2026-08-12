# Phase 1 Scraper Test Framework — Agent Handoff Prompt

## Mission
**Fix the CSV parsing issue preventing accurate result reporting in the 17-person test framework.**

Current status:
- ✅ HTML extraction working (brokers return data correctly)
- ✅ Test framework running (17 profiles × 3 brokers = results)
- ❌ CSV parsing broken (some fields truncated/missing in output)

The extraction logic is solid. The problem is in how we're aggregating/writing those results to CSV.

---

## What You're Working With

### Location
`/Users/jameso/DevWork/vanyshr-stack/vanyshr-scraper-sequence/vanyshr-scraper-lab/`

### Key Files
- `test_all_17_profiles.py` — The test runner (THE ENTRY POINT)
- `sequence_runner.py` — Broker orchestration + field extraction (problem likely here)
- `data_models.py` — SummaryResult dataclass (verify field definitions)
- Sample output: `/Users/jameso/Downloads/Test_Profiles_-_detailed_results.csv`

---

## The Problem (Detailed)

### Symptom
Running `python3 test_all_17_profiles.py` produces `/Users/jameso/Downloads/Test_Profiles_-_detailed_results.csv` with incomplete data:

**Example issues:**
```
Phones truncated:    "(816) 632-" instead of "(816) 632-2218"
Email blank:         "" when it should be "r@yahoo.com, j@hotmail.com"
Aliases empty:       "" when extracted data exists
Relatives missing:   Similar blanks despite successful extraction
```

### Root Cause Candidates

**Hypothesis 1: `sequence_runner.py` `_scrape_broker()` field extraction (Lines ~270)**
- Using `getattr(summary, 'field', getattr(summary, 'fieldPreview', ''))`
- Possible issues:
  - Field names don't match broker response structure
  - Getattr fallback not working (both variants missing)
  - Data being truncated during assignment
  - Type conversion issues (list → str concatenation)

**Hypothesis 2: `test_all_17_profiles.py` CSV writing logic**
- CSV fieldnames mismatch
- CSV module truncating fields
- Row overwrites instead of appends
- String encoding issues

**Hypothesis 3: Data model definition**
- `data_models.py` SummaryResult fields not initialized properly
- Default empty strings masking real values
- Field type mismatches

**Hypothesis 4: Context.dev API response parsing**
- HTML scraper not extracting complete values
- AnyWho data-content reconstruction cutting off prematurely

---

## How to Debug (Step-by-Step)

### Step 1: Run a Single-Profile Test
```bash
# Edit test_all_17_profiles.py, change line ~50 to test just one profile:
# profiles = profiles[:1]  # Just first profile

python3 test_all_17_profiles.py 2>&1 | tee debug.log
```

### Step 2: Inspect Broker Output
Add logging to `sequence_runner.py` `_scrape_broker()` around line 270:

```python
def _scrape_broker(self, broker_name, params):
    # ... existing code ...
    
    summary_results = broker_result.get('summary_results', [])
    for summary_dict in summary_results:
        summary = SummaryResult(**summary_dict)
        
        # ← ADD DEBUG LOGGING HERE
        print(f"\n[DEBUG] Broker: {broker_name}")
        print(f"  Raw phone: {summary_dict.get('phone', 'N/A')}")
        print(f"  Raw email: {summary_dict.get('email', 'N/A')}")
        print(f"  SummaryResult phone: {summary.phone}")
        print(f"  SummaryResult email: {summary.email}")
        
        # Continue with existing extraction...
```

### Step 3: Check CSV Row Before Write
In `test_all_17_profiles.py`, add logging before CSV write:

```python
# Before: csv_writer.writerow(detail_row)
print(f"[CSV DEBUG] Writing detail row: {detail_row}")
print(f"  Phone value: '{detail_row.get('phones', '')}'")
print(f"  Email value: '{detail_row.get('emails', '')}'")

# Then write:
csv_writer.writerow(detail_row)
```

### Step 4: Compare JSON vs CSV
After single-profile test:
1. Check raw broker JSON (if logged)
2. Check intermediate CSV
3. Compare field-by-field: which ones match, which are truncated?

---

## Code Inspection Checklist

### `sequence_runner.py` (Lines ~270)
```python
def _scrape_broker(self, broker_name, params):
    # [Line 270 region] Field extraction:
    # ✓ Check: Does 'phone' in broker_result match actual response key?
    # ✓ Check: Is getattr() catching both 'phone' and 'phonePreview' correctly?
    # ✓ Check: Are values complete strings, not truncated?
    # ✓ Check: Type handling (list of strings → comma-separated string)?
```

### `test_all_17_profiles.py` (CSV Writing Section)
```python
# ✓ Check: CSV fieldnames match your dict keys?
# ✓ Check: detail_row dict has all expected fields before writerow()?
# ✓ Check: No CSV quoting/escaping issues?
# ✓ Check: File opened in correct mode (w, not a)?
```

### `data_models.py` (SummaryResult Definition)
```python
@dataclass
class SummaryResult:
    # ✓ Check: All fields present?
    # ✓ Check: Default values not masking real data?
    # ✓ Check: Field types match how they're used (str, not list)?
```

---

## Expected Behavior (When Fixed)

All fields should be complete and populated:

```
search_ID,profile_number,target,...,phones,emails,aliases,relatives
ocker,1,fps,...,"(816) 632-2218, (816) 225-8592","ja_studly@hotmail.com","James Allen Oehring Jr.","Rickilinda Oehring, ..."
ocker,NO_RESULTS,npd,...,,,,
ocker,1,anywho,...,"(816) 632-2218, (270) 678-9012","r@yahoo.com, j@hotmail.com","Christophe James Ocker","Deena Ocker, James Ocker"
```

No truncation, no blanks where data should be.

---

## Testing the Fix

### Run Full Test
```bash
python3 test_all_17_profiles.py
```

### Spot-Check Results
Compare CSV against known profiles (all are real people James knows):
- **oehring (James Oehring, Cameron, MO)**
  - Should have: age ~61-62, address with "Lovers Ln", phone (816) 632-2218, relative Rickilinda Oehring
  
- **clark (Lucas Clark, Kansas City, MO)**
  - Should have: multiple matches, ages 30-68, various addresses

### Success Criteria
✅ All 17 profiles tested
✅ No truncated phone numbers
✅ No blank email/alias/relative fields (where data exists)
✅ Spot-check matches known profiles
✅ CSV opens cleanly in Excel/Sheets

---

## Debugging Tips

**If phones are truncated:** Check AnyWho extraction, data-content reconstruction, phone regex
**If email/alias fields blank:** Verify broker extraction includes them, SummaryResult initialization correct
**If CSV corrupt:** Check write mode (w, not a), fieldnames, no duplicate headers
**If data disappears:** Check CSV writer isn't overwriting rows

---

## Quick Reference

**Test data:** 17 hardcoded profiles in test_all_17_profiles.py (all known people)
**Output:** `/Users/jameso/Downloads/Test_Profiles_-_detailed_results.csv`
**Brokers tested:** FPS, NPD, AnyWho (Phase 1 summary scrapers only)
**Expected runtime:** ~52 seconds for full test

---

## Success Outcome

When you complete this:
1. ✅ CSV parsing issue identified and fixed
2. ✅ All fields (age, address, phone, email, aliases, relatives) populate correctly
3. ✅ 17-person test re-run produces clean, complete results
4. ✅ Results available for spot-checking
5. ✅ JOURNAL.md updated with the fix

---

**You have everything you need. The extraction logic is working — this is just a data aggregation/formatting issue. Go fix the CSV.**
