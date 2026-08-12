# Phase 1 Scraper — Handoff

> **Superseded.** The previous version of this file asked the next agent to fix
> a "CSV parsing issue". There was no CSV bug. The real defects were in
> extraction and are now fixed and covered by tests. That earlier diagnosis is
> preserved below under "What the original handoff got wrong" so the reasoning
> isn't lost — do not act on it.

## Current status

Phase 1 (summary search across FPS, NPD, AnyWho) extracts complete data and is
regression-covered by fixture-driven tests that need no network.

Last full run: 17 profiles, 104 rows, ~3 s/profile.

| | rows | age | address | phone | email | aliases | relatives |
|---|---|---|---|---|---|---|---|
| FPS | 40 | 36 | 38 | — | — | — | 38 |
| NPD | 4 | 4 | 4 | 4 | 4 | — | 4 |
| AnyWho | 28 | 28 | 28 | 23 | 15 | 27 | 26 |

0 truncated phones, 0 truncated emails.

FPS dashes are correct, not gaps: the FPS **summary** page carries no phone or
personal email at all. Those come from the full profile page (Phase 2). This is
asserted deliberately in `tests/test_fps_html_scraper.py` so nobody re-opens it.

## How to run

```bash
# Unit tests — no network, no API key
cd tests && python3 -m pytest -q --ignore=./test_scrape_runner.py

# Full 17-profile live run (~50 context.dev calls, ~$0.05)
python3 test_all_17_profiles.py
# -> /Users/jameso/Downloads/Test_Profiles_-_detailed_results.csv

# Re-capture broker HTML fixtures (only when a broker changes its markup)
python3 tests/capture_fixtures.py --force
```

## What was actually wrong

**1. AnyWho `_reconstruct_with_data_content()` was not recursive.**
AnyWho blurs sensitive values: visible text holds the leading fragment, the rest
sits in a `data-content` attribute on an *empty* nested span rendered via CSS
`before:content-[attr(data-content)]`:

```html
<div><span><span>(816) 632-</span>
     <span class="blur-sm" data-content="2218"></span></span></div>
```

The helper's comment claimed recursion but the code called
`child.get_text(strip=True)`, which returns visible text only and discards every
nested `data-content`. The blurred span is two levels deep, so it was always
lost — corrupting phones, email local parts and street numbers at once.

**2. AnyWho age was never extracted.** `find('span', string=re.compile(r'Age'))`
never matched because the age span also contains an `<svg>`, and bs4's `string=`
only matches single-child tags.

**3. NPD ignored its own JSON-LD.** The rendered card has only name, age and
city/state. Phones, emails, street address and relatives live solely in the
embedded JSON-LD `Person` block. `_extract_jsonld_person` already existed but
was used only on the profile path.

**4. FPS read link text instead of the title attribute.** The address link's
text is `Cameron, MO`; the street address is in `title`
(`413 Lovers Ln, Cameron MO 64429`). FPS relatives were present under
`<h4>Relatives:</h4>` and simply not parsed.

## Why no test caught it

The pre-existing suite covers the old `workers/` modules (`npd_scraper`,
`anywho_test`). Nothing imported any `*_html_scraper.py` — the modules the
pipeline actually runs. A green "46/46 passed, phone reassembly ✅" was testing
code that is not in the pipeline.

Tests added (all fixture-driven, no network):

- `tests/test_anywho_html_scraper.py`, `test_fps_html_scraper.py`,
  `test_npd_html_scraper.py` — assert **completeness**, not presence: full
  `(NNN) NNN-NNNN`, email local part longer than one character, addresses
  retaining house numbers
- `tests/test_scrape_broker_contract.py` — the three brokers expose three
  different `SummaryResult` shapes bridged by a getattr chain in
  `sequence_runner.py`; asserts no populated field silently becomes `""`
- `tests/data_quality.py` — shared assertions
- `tests/fixtures/{anywho,fps,npd}/` — real captured broker HTML

## Open items

1. **NPD returns NO_RESULTS for 13/17 profiles.** Extraction is verified correct
   (the 4 that return are 100% populated), so this is either genuine coverage or
   an over-strict city/state URL filter. Try the same names without the city
   segment before concluding NPD is thin.
2. **AnyWho match quality.** For `oehring`, AnyWho returns a 37-year-old "James
   A Oehring" in Kansas City whose AKA is "James Allen Oehring Jr." — likely the
   son, not the 61/62-year-old in Cameron that FPS and NPD return. Dedup must
   not merge them.
3. **Pre-existing broken test:** `tests/test_scrape_runner.py` imports
   `transform_fps_result`, but `scrape_result_transformer.py` defines
   `transform_fps_response`. It fails at collection and is excluded above.
   Untouched here — it predates this work.
4. **No DB schema is being validated against yet.** Current bar is "complete and
   untruncated, matching what the broker page shows". When a target schema
   exists, extend `tests/data_quality.py` to assert the destination contract.

---

## What the original handoff got wrong

Preserved for reference — **do not act on this.**

It claimed: *"HTML extraction working ✅ / CSV parsing broken ❌ — the
extraction logic is solid, this is just a data aggregation/formatting issue.
Go fix the CSV."* It ranked "Context.dev API response parsing" last of four
hypotheses.

That was inverted. The CSV writer was always correct — it opens `'w'`, calls
`writeheader()` once, and uses `DictWriter` properly; it wrote faithfully what
it was handed. The evidence pointing at extraction was already visible in the
sample output:

- truncation was *systematic* — every AnyWho phone lost exactly its last four
  digits; a CSV bug does not clip the same four characters every time
- emails were *truncated, not blank* (`ja_studly@hotmail.com` →
  `j@hotmail.com`), which is the same blur boundary
- addresses lost their house numbers — again the same boundary
- the "row 29 has an email, row 30 is blank → overwrite bug" reading was a
  misinterpretation; those are two different result cards from one search
