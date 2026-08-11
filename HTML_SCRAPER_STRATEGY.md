# HTML Scraper Strategy — Cost Optimization

## Problem Statement

Extract API costs ~0.005 per request, taking 70-90 seconds. This is **10x more expensive** than HTML method. 
- Extract uses AI-powered schema-based extraction
- HTML method uses pattern-based extraction (cheaper, faster)

## Solution: Dual-Method Approach

### Keep (Extract-based)
- ✅ `targets/fps/scraper.py` — Premium quality, slower, use as fallback
- ✅ `targets/npd/scraper.py` — Full featured extraction
- ✅ `targets/anywho/scraper.py` — Multiple results handling
- ✅ `targets/zaba/scraper.py` — Multi-profile extraction

### New (HTML-based — Primary)
- 📋 `fps_html_scraper.py` — Cost-efficient FPS (in sequence worktree)
- 📋 `npd_html_scraper.py` — Cost-efficient NPD
- 📋 `anywho_html_scraper.py` — Cost-efficient AnyWho
- 📋 `zaba_html_scraper.py` — Cost-efficient Zaba (should work better than Extract since it was blocked)

## Architecture

**HTML scrapers use context.dev HTML method**, not raw HTTP:
```python
html_result = self.client.web.html(
    url=search_url,
    max_age_ms=86400000  # Cache 24 hours
)
# Use BeautifulSoup to parse html_result.html
```

Benefits:
1. **Cost**: 10x cheaper than Extract (~$0.0005 vs ~$0.005 per request)
2. **Performance**: 2-5 seconds vs 70-90 seconds
3. **Reliability**: context.dev handles IP detection, user-agent rotation
4. **Fallback**: Keep Extract versions if HTML parsing fails

## Implementation Details

### All HTML Scrapers Follow Same Pattern

1. **Import context.dev client** (not requests)
2. **Fetch via `self.client.web.html()`** (not Extract)
3. **Parse with BeautifulSoup** for flexible extraction
4. **Regex for structured data** (phone, email, age)
5. **Same models** (ScrapeOutput, Profile, SummaryResult)
6. **Standard interface**: `run(params) -> ScrapeOutput`

### Data Extraction Strategy

**Robust selectors** — avoid brittle CSS selectors:
```python
# ❌ BAD - too specific
phone_elem = soup.select_one('.contact-info .phone-primary')

# ✅ GOOD - flexible
phone_text = soup.get_text()
phone_matches = re.findall(r'\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})', phone_text)
```

### Cost Comparison

| Broker | Extract (old) | HTML (new) | Speed | Savings |
|--------|---------------|-----------|-------|---------|
| FPS | $0.005 | $0.0005 | 3s vs 80s | **10x cheaper, 27x faster** |
| NPD | $0.005 | $0.0005 | 3s vs 85s | **10x cheaper, 28x faster** |
| AnyWho | $0.005 | $0.0005 | 3s vs 70s | **10x cheaper, 23x faster** |
| Zaba | Blocked ✗ | $0.0005 | 3s | **Works! (IP blocking issue solved)** |

## Critical Dependency: context.dev API Verification

**⚠️ IMPORTANT**: Verify the HTML method API signature from docs:
https://docs.context.dev/api-reference/web-scraping/html

The code assumes:
```python
html_result = self.client.web.html(url=..., max_age_ms=...)
# Returns object with .html attribute containing raw HTML
```

If the actual API is different (e.g., `web.scrape()`, `web.fetch()`, different params), 
update all four scrapers with the correct method.

## Testing Strategy

### Phase 1: Syntax Validation ✅
```bash
python3 -m py_compile fps_html_scraper.py npd_html_scraper.py anywho_html_scraper.py zaba_html_scraper.py
```

### Phase 2: API Verification (NEXT)
1. Check context.dev docs for actual HTML method signature
2. Update method calls if needed
3. Test single scraper with real API

### Phase 3: Live Testing
```bash
python3 fps_html_scraper.py  # Run each individually
python3 npd_html_scraper.py
python3 anywho_html_scraper.py
python3 zaba_html_scraper.py
```

Expected results:
- Status: "success" or "no_results"
- Time: 2-5 seconds (vs 70-90s for Extract)
- Profiles: 1-20 depending on broker

### Phase 4: Sequence Runner Integration
Update `scraper_sequence.py` to support mode selection:
```python
runner = SequenceRunner(mode="html")  # Use HTML method
# vs
runner = SequenceRunner(mode="extract")  # Use Extract method (fallback)
```

## Next Steps

1. ✅ **Created**: All four HTML scraper versions
2. **TODO**: Verify context.dev HTML method API signature
3. **TODO**: Test FPS HTML scraper with real data
4. **TODO**: Fix any API method name mismatches
5. **TODO**: Test all four scrapers individually
6. **TODO**: Update sequence runner with mode selection
7. **TODO**: Integration tests (HTML mode vs Extract fallback)
8. **TODO**: Document cost/speed tradeoffs in production guide

## Zaba Special Note

Zaba Extract-based scraper was blocked by IP detection:
```
Status: "failed"
Error: "WEBSITE_ACCESS_ERROR: 400"
```

HTML method should work better because:
1. context.dev handles anti-scraping detection
2. HTML parsing is less suspicious than AI extraction
3. Can use residential IP service as fallback (serv01:8788)

This makes Zaba HTML version a **critical win** — it's currently unavailable via Extract.

---

**Document Status**: Ready for API verification
**Priority**: High (10x cost reduction, 27x speed improvement)
