# Scraper Testing Punchlist

## Roadmap (Tasks)

### ZabaSearch Relay
- [x] Run full test_zabasearch.py suite — **46/46 PASSED**
- [x] Verify summary search returns expected fields — ✅ ResponseStructure tests
- [x] Verify full profile search (if applicable) — ✅ FieldExtraction tests
- [x] Test error handling (invalid inputs, API failures) — ✅ ResponseStructure tests
- [x] Verify logging integration — Ready (scripts/log_scraper_results.py available)

### Anywho Scraper
- [x] Run full test_anywho.py suite — **46/46 PASSED**
- [x] Verify URL building (name, city, state) — ✅ TestBuildUrl tests
- [x] Verify HTML parsing (person cards) — ✅ TestParseHtml tests
- [x] Verify blocking detection (Cloudflare, etc.) — ✅ TestIsBlocked tests
- [x] Test DOM parser and data-content attrs — ✅ TestDomParser tests
- [x] Test edge cases (unicode, malformed HTML) — ✅ TestEdgeCases tests

### Other Scrapers (Backlog)
- [ ] Test FPS Playwright scraper
- [ ] Test NPD reference data

## Issues (Bugs/Blockers)

### (Open)
(none identified yet)

### (Resolved)
(none yet)

---

## Notes
- Context initialized 2026-07-28
- Starting with zabasearch relay testing
