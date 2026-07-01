# AnyWho Scrape Spec

Reference spec for scraping people-search results from **anywho.com**.
Source of truth for the production scraper:
`supabase/functions/_shared/scrapers/AnyWhoScraper.ts`.

A standalone, dependency-free tester that implements this spec lives next to
this file: [`anywho_test.py`](./anywho_test.py).

---

## 1. Site shape (important)

anywho.com is a **Next.js (App Router) + Payload CMS** app.

- The homepage search form `https://www.anywho.com/?fullName=...&cityState=...`
  **does not return results.** It rewrites to a static, prerendered landing
  page (`x-nextjs-rewritten-path: /name/landing`, `x-nextjs-cache: HIT`) with
  zero match data in the HTML. Do not scrape this URL.
- Results live on a **path-based** URL (a server-rendered list/city view). The
  match cards are present in the initial HTML response — **no JS execution
  required** to read names, ages, addresses, phones, relatives, and the detail
  link. A plain `GET` is enough when not Cloudflare-challenged.

---

## 2. URL construction

```
Search (name only):   https://www.anywho.com/people/{first}+{last}
Search (+ state):     https://www.anywho.com/people/{first}+{last}/{state-name}
Search (+ city):      https://www.anywho.com/people/{first}+{last}/{state-name}/{city-slug}
```

### Slug rule (`formatNameForUrl`)
Applied to each name part, the city, and (as a fallback) the state:
1. lowercase
2. replace every non-`[a-z0-9]` char with `-`
3. collapse repeated `-`
4. trim leading/trailing `-`

The two name parts are slugged individually and joined with a literal `+`
(e.g. `John` + `Fryer` → `john+fryer`).

### State map (abbreviation → full slug)
`KS → kansas`, `MO → missouri`, `DC → district-of-columbia`,
`NH → new-hampshire`, etc. Full table in `AnyWhoScraper.ts` / the tester.
If an unknown abbreviation is passed, fall back to `state.toLowerCase()`.

### Worked example
`John Fryer`, `Mission Hills`, `KS`:
```
https://www.anywho.com/people/john+fryer/kansas/mission-hills
```

---

## 3. Anti-bot / fetch routing

Cloudflare guards the site and is **inconsistent** — a direct residential GET
often succeeds, but datacenter IPs get challenged. Production fetch order:

1. **CF Worker relay (primary)** — `CF_RELAY_URL?url=<encoded>` with header
   `x-relay-token: <CF_RELAY_TOKEN>`, 8s timeout. Controlled + reliable.
2. **Free CORS proxies (fallback)**, 6s each, in order:
   - `https://corsproxy.io/?`
   - `https://api.codetabs.com/v1/proxy?quest=`
   - `https://api.allorigins.win/raw?url=`

Each proxy/relay URL is `proxy + encodeURIComponent(targetUrl)`.

### Block detection (`isBlockedResponse`)
Treat the response as blocked/empty and try the next route if the HTML:
- contains `Just a moment...`
- contains `Checking your browser`
- contains `Access denied`
- is shorter than **500 bytes**

Use a desktop Chrome User-Agent on every request:
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36
```

---

## 4. Blurred-digit reassembly (the key trick)

AnyWho hides parts of phone numbers and street numbers behind CSS — the real
digits sit in a `data-content` attribute on a blurred span and are rendered via
`before:content-[attr(data-content)]`:

```html
<span data-content="6531" class="blur-sm before:content-[attr(data-content)]"></span>
```

The blurred fragment can appear **before** or **after** the visible text:

| Field   | Layout                                   | Reassembled                       |
|---------|------------------------------------------|-----------------------------------|
| Address | `data-content="6531"` + ` Overbrook Rd, Mission Hills, KS` | `6531 Overbrook Rd, Mission Hills, KS` |
| Unit #  | `... Unit ` + `data-content="607"` + `, Atlanta, GA`       | `Peachtree Rd Ne, Unit 607, Atlanta, GA` |
| Phone   | `(816) 210-` + `data-content="5210"`     | `(816) 210-5210`                  |

**Rule:** to read any value, walk the DOM in document order and, for each node,
emit its `data-content` value (if present) in place, otherwise its text. Do not
rely on `textContent` alone — it omits the blurred digits. Do not assume the
blur span is always the previous/next sibling; order varies by field.

---

## 5. Result-card HTML structure (search/list page)

Each match is a card. Anchor extraction on the name `<h2>`, then walk up to the
ancestor that also contains a `Lives in:` `<h3>`.

```html
<h2>John Fryer</h2><span>, </span><span ...>Age 36<svg/></span>
...
<a href="/people/john+fryer/missouri/kansas+city/a10196594199847">
  <button ...>View Details</button>
</a>
...
<h3>AKA:</h3>              <div>John Burnell Fryer<span> • </span></div> ...
<h3>Lives in:</h3>        <div><span><span data-content="6531"></span><span> Overbrook Rd, Mission Hills, KS</span></span></div>
<h3>Used to live in:</h3> <div>...• separated entries, each with blurred house number...</div>
<h3>Phone number(s):</h3> <div>...• separated, each "(NXX) NXX-" + data-content last4...</div>
<h3>May be related to:</h3><div>Name • Name • ... +N more</div>
```

### Fields extracted per card
| Field          | Source                                                        |
|----------------|---------------------------------------------------------------|
| `name`         | the card's `<h2>` text                                         |
| `age`          | `Age (\d+)` adjacent to the `<h2>`                             |
| `lives_in`     | `Lives in:` value, blur-reassembled (current address)         |
| `used_to_live` | `Used to live in:` values, `•`-separated, blur-reassembled    |
| `phones`       | `Phone number(s):` values, `•`-split, blur-reassembled, ≥10 digits |
| `aka`          | `AKA:` value(s)                                                |
| `related`      | `May be related to:` value (names, may end in `+N more`)       |
| `detail_link`  | `<a href="/people/.../a{digits}">` → absolute URL             |

Headings to **skip** when scanning `<h2>`s: `Filter by State`, `Filter by Age`,
`... Summary`, `... in Numbers`, `... F.A.Q.`, `Find People by Area Code`.

---

## 6. Detail page (`/people/.../a{id}`)

Following the `detail_link` yields a richer per-person page parsed by
`parseDetailFromHtml` in `AnyWhoScraper.ts`. Key selectors / sections:

- Name: `h1.text-display-sm` (or first `h1`); age from trailing `, NN`.
- Phones: `#phones .show-more-item` — visible span + `span[data-content]` last4;
  carrier/type from `.text-body-sm` split on `•`.
- Emails: `#emails` (and `[id*=email]`/`[class*=email]`); regex incl. masked
  `m*****@aol.com`.
- Addresses: `#addresses h4` — street number is **blurred** (same data-content
  trick); city/state/zip from container text; date range `YYYY–YYYY|Present`;
  property type (Single Family / Condo / …).
- Relatives: `#... ` body-text patterns `Name (Female|Male) • Age`.
- Assets / net worth, legal records (`#court-records`), background records
  (`#personal-history`, plus birth/death body-text fallbacks).

The standalone tester currently parses the **search/list** page only; add a
`--details` mode to follow the link if detail-page fields are needed.

---

## 7. Quick test

```bash
cd workers/anywho
./anywho_test.py "John" "Fryer" "Mission Hills" KS   # name + city + state
./anywho_test.py James Oehring                       # name-only (national)
./anywho_test.py John Fryer "Mission Hills" KS --raw # dump HTML to /tmp/anywho_raw.html
```

Expected for the first command: 1 card — `John Fryer, Age 36`,
`6531 Overbrook Rd, Mission Hills, KS`, four `(816) …` phones, AKA + relatives,
and a `…/kansas+city/a10196594199847` detail link.

Exit codes: `2` fetch error, `3` Cloudflare-blocked/empty, `0` parsed (may be 0
cards if no match).
