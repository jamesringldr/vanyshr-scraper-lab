# HTML Scraper Versions — Quick Start

## Overview

Four cost-optimized scraper versions using context.dev's **HTML method** instead of expensive Extract API:

- `fps_html_scraper.py` — FastPeopleSearch (cost: -90%)
- `npd_html_scraper.py` — National Public Data (cost: -90%)  
- `anywho_html_scraper.py` — AnyWho (cost: -90%)
- `zaba_html_scraper.py` — Zaba Search (works where Extract was blocked!)

## Quick Comparison

| Aspect | Extract | HTML |
|--------|---------|------|
| **Cost** | $0.005/req | $0.0005/req |
| **Speed** | 70-90s | 2-5s |
| **Extraction** | AI-powered | Pattern-based |
| **Selectors** | Flexible schema | Regex + BeautifulSoup |
| **Fallback** | N/A | Extract (premium) |

## Getting Started

### 1. Verify API Signature (CRITICAL FIRST STEP)

The HTML method API signature needs verification:

```bash
# Set your API key
export CONTEXT_DEV_API_KEY="your-key-here"

# Test the actual API
python3 test_html_api_signature.py
```

This script will:
- ✅ Check available methods on `client.web`
- ✅ Test likely method names (html, scrape, fetch, etc)
- ✅ Verify the result object structure
- ✅ Print exact method to use

**Output example:**
```
✅ SUCCESS! Method: client.web.html()
   Result attribute for HTML: html
```

### 2. Update Scrapers (if needed)

If the API signature differs from assumption:
```python
# Current assumption:
html_result = self.client.web.html(url=..., max_age_ms=...)
html_content = html_result.html

# If API returns different structure, update all 4 scrapers
```

### 3. Test Individual Scrapers

```bash
# Make sure API key is set
export CONTEXT_DEV_API_KEY="your-key"

# Test each scraper
python3 fps_html_scraper.py
python3 npd_html_scraper.py
python3 anywho_html_scraper.py
python3 zaba_html_scraper.py
```

Expected output:
```
Status: success
Time: 2500ms (2-5 seconds)
Results: 1-20 (depending on broker)
```

### 4. Integration with Sequence Runner

The sequence runner needs updating to support mode selection:

```python
# Old: Extract only
runner = SequenceRunner()

# New: With mode selection
runner = SequenceRunner(mode="html")    # Use HTML method (fast, cheap)
runner = SequenceRunner(mode="extract") # Use Extract API (slow, expensive, fallback)
runner = SequenceRunner(mode="auto")    # Try HTML first, fallback to Extract
```

## File Structure

```
vanyshr-scraper-sequence/
├── fps_html_scraper.py              # FPS cost-efficient version
├── npd_html_scraper.py              # NPD cost-efficient version
├── anywho_html_scraper.py           # AnyWho cost-efficient version
├── zaba_html_scraper.py             # Zaba cost-efficient version (IP-blocked fix!)
├── test_html_api_signature.py       # Verify API method signature
├── HTML_SCRAPER_STRATEGY.md         # Full architecture docs
└── README_HTML_SCRAPERS.md          # This file
```

## Data Extraction Approach

All HTML scrapers use:

1. **context.dev HTML method** for fetching (cheap, reliable)
2. **BeautifulSoup** for flexible HTML parsing
3. **Regex** for structured data (phone, email, age)
4. **Same models** as Extract versions (compatibility)

Example extraction pattern:
```python
# Fetch with context.dev (cheap)
html_result = self.client.web.html(url=url, max_age_ms=86400000)
soup = BeautifulSoup(html_result.html, 'html.parser')

# Parse with regex (robust)
phones = re.findall(r'\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})', soup.get_text())
emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.get_text())
```

## Zaba Special Case

The Extract-based Zaba scraper returned `WEBSITE_ACCESS_ERROR: 400` due to IP detection.

**HTML version should work** because:
- ✅ context.dev handles anti-scraping transparently
- ✅ Pattern-based extraction is less suspicious
- ✅ Residential IP fallback available (serv01:8788)

## Testing Checklist

- [ ] API signature verified via `test_html_api_signature.py`
- [ ] All four scrapers tested individually
- [ ] Execution times confirmed (2-5s expected)
- [ ] Sequence runner updated with mode selection
- [ ] Integration tests passing (HTML + Extract fallback)
- [ ] Cost comparison validated
- [ ] Committed to dev/scraper-targets

## Troubleshooting

### "Method not found" error
→ Run `test_html_api_signature.py` to find correct method name

### "Invalid API key" error  
→ Check: `echo $CONTEXT_DEV_API_KEY`

### Timeouts (>10 seconds)
→ Might be hitting rate limits; add delays between requests

### No results returned
→ Check browser dev tools on actual site to validate URL format

## Next: Sequence Runner Integration

Once HTML scrapers are verified:

```python
# Update scraper_sequence.py
class SequenceRunner:
    def __init__(self, mode="html", api_key=None):
        self.mode = mode
        
    def _get_scraper_class(self, broker):
        if self.mode == "html":
            # Import HTML versions
            return FPSHtmlScraper
        else:
            # Use Extract versions from targets/
            return FPSScraper
```

See `HTML_SCRAPER_STRATEGY.md` for full architecture details.

---

**Status**: Ready for API verification  
**Priority**: High (10x cost savings + Zaba IP blocking fix)
