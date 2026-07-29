#!/usr/bin/env python3
"""
Standalone AnyWho scrape tester — throwaway stand-in for scraper-lab's
test-quickscan.sh while the repo is re-cloned.

Mirrors supabase/functions/_shared/scrapers/AnyWhoScraper.ts:
  - builds the PATH-based URL  /people/{first}+{last}/{state-name}/{city-slug}
    (NOT the /?fullName=&cityState= homepage form, which 302s to a static
     landing page with no results)
  - reassembles digits hidden in <span data-content="NNNN"> blur spans,
    walking nodes in document order so it works whether the blurred part
    comes first (house numbers) or last (phone digits).

Usage:
  ./anywho_test.py "John" "Fryer" "Mission Hills" KS
  ./anywho_test.py John Fryer            # name-only (no city/state)
  ./anywho_test.py John Fryer --raw      # also dump fetched HTML to /tmp
"""
import sys, re, urllib.request, urllib.error, unicodedata
from html.parser import HTMLParser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

STATE_NAMES = {
    "AL":"alabama","AK":"alaska","AZ":"arizona","AR":"arkansas","CA":"california",
    "CO":"colorado","CT":"connecticut","DE":"delaware","DC":"district-of-columbia",
    "FL":"florida","GA":"georgia","HI":"hawaii","ID":"idaho","IL":"illinois",
    "IN":"indiana","IA":"iowa","KS":"kansas","KY":"kentucky","LA":"louisiana",
    "ME":"maine","MD":"maryland","MA":"massachusetts","MI":"michigan",
    "MN":"minnesota","MS":"mississippi","MO":"missouri","MT":"montana",
    "NE":"nebraska","NV":"nevada","NH":"new-hampshire","NJ":"new-jersey",
    "NM":"new-mexico","NY":"new-york","NC":"north-carolina","ND":"north-dakota",
    "OH":"ohio","OK":"oklahoma","OR":"oregon","PA":"pennsylvania","RI":"rhode-island",
    "SC":"south-carolina","SD":"south-dakota","TN":"tennessee","TX":"texas",
    "UT":"utah","VT":"vermont","VA":"virginia","WA":"washington",
    "WV":"west-virginia","WI":"wisconsin","WY":"wyoming",
}

def slug(s):
    """formatNameForUrl: lowercase, non-alphanumerics -> '-', collapse, trim."""
    s = s.lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")

def build_url(first, last, city=None, state=None):
    name = f"{slug(first)}+{slug(last)}"
    url = f"https://www.anywho.com/people/{name}"
    if state:
        url += "/" + STATE_NAMES.get(state.upper(), state.lower())
        if city:
            url += "/" + slug(city)
    return url

# ---- tiny DOM that preserves blurred data-content in document order ----------
class Node:
    __slots__ = ("tag", "attrs", "children", "parent")
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []
    def text(self):
        out = []
        for c in self.children:
            out.append(c if isinstance(c, str) else c.text())
        return "".join(out)
    def walk(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.walk()

VOID = {"br","img","input","meta","link","hr","source","area","col","base"}

class DOM(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.cur = self.root
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        n = Node(tag, a, self.cur)
        self.cur.children.append(n)
        # the blurred digits ARE this span's rendered content -> insert in order
        if "data-content" in a:
            n.children.append(a["data-content"])
        if tag not in VOID:
            self.cur = n
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)
    def handle_endtag(self, tag):
        node = self.cur
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.cur = node.parent
    def handle_data(self, data):
        self.cur.children.append(data)

def clean(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip(" ••-").strip()

# ---- fetch -------------------------------------------------------------------
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "ignore")

def is_blocked(html):
    return ("Just a moment" in html or "Checking your browser" in html
            or "Access denied" in html or len(html) < 200)

# ---- parse cards -------------------------------------------------------------
def section_after(h3_node):
    """Extract value from h3 header (either from text after colon or from siblings)."""
    h3_text = h3_node.text()
    if ":" in h3_text:
        parts = h3_text.split(":", 1)
        if len(parts) > 1:
            return clean(parts[1])
    if h3_node.parent is None:
        return ""
    found = False
    vals = []
    for c in h3_node.parent.children:
        if found:
            if isinstance(c, Node):
                vals.append(c.text())
            elif isinstance(c, str) and c.strip():
                vals.append(c)
        elif isinstance(c, Node) and c is h3_node:
            found = True
    return clean(" ".join(vals)) if vals else ""

NAME_RE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z.]*){1,3}$")

def parse(html):
    dom = DOM()
    dom.feed(html)
    nodes = list(dom.root.walk())

    # Anchor each result on its name <h2> (matches AnyWhoScraper.ts), then the
    # card is the nearest ancestor that also contains a "Lives in:" section.
    results, seen = [], set()
    for h2 in (n for n in nodes if n.tag == "h2"):
        nm = clean(h2.text())
        low = nm.lower()
        if not NAME_RE.match(nm) or "summary" in low or "filter" in low \
                or "f.a.q" in low or "numbers" in low:
            continue
        card, hops = h2.parent, 0
        while card is not None and hops < 9:
            if any(c.tag == "h3" and clean(c.text()).lower().startswith("lives in")
                   for c in card.walk()):
                break
            card, hops = card.parent, hops + 1
        if card is None or id(card) in seen:
            continue
        seen.add(id(card))
        results.append(extract(card, nm))
    return results

def card_hrefs(card):
    return " ".join(n.attrs.get("href", "") for n in card.walk() if n.tag == "a")

def headers_map(card):
    """Map of lowercased h3 header text -> reconstructed value block."""
    out = {}
    for h3 in (n for n in card.walk() if n.tag == "h3"):
        h3_text = clean(h3.text())
        if ":" in h3_text:
            label_part = h3_text.split(":", 1)[0]
        else:
            label_part = h3_text
        label = label_part.lower()
        if label:
            out.setdefault(label, []).append(section_after(h3))
    return out

def extract(card, name):
    hm = headers_map(card)
    def first(*keys):
        for k in keys:
            for label, vals in hm.items():
                if label.startswith(k):
                    v = clean(vals[0])
                    if v:
                        return v
        return None

    age_m = re.search(r"Age\s+(\d{1,3})", card.text())
    age = age_m.group(1) if age_m else None
    aka = first("aka")
    lives = first("lives in")
    used = first("used to live")
    related = first("may be related", "related to")

    # phones: extract all digit sequences from "phone number" headers, reconstruct from data-content
    phones = []
    for label, vals in hm.items():
        if label.startswith("phone"):
            for v in vals:
                digits_only = re.sub(r"\D", "", v)
                if len(digits_only) >= 10:
                    formatted = re.sub(r"(\d{3})(\d{3})(\d{4})", r"\1-\2-\3", digits_only)
                    phones.append(formatted)

    # detail link (absolute)
    detail = None
    for n in card.walk():
        if n.tag == "a" and n.attrs.get("href", "").startswith("/people/") \
                and re.search(r"/a\d+$", n.attrs["href"]):
            href = n.attrs["href"]
            detail = href if href.startswith("http") else "https://www.anywho.com" + href
            break

    return {"name": name, "age": age, "aka": aka, "lives_in": lives,
            "used_to_live": used, "phones": phones, "related": related,
            "detail_link": detail}

# ---- main --------------------------------------------------------------------
def main():
    args = [a for a in sys.argv[1:] if a != "--raw"]
    raw = "--raw" in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    first, last = args[0], args[1]
    city = args[2] if len(args) > 2 else None
    state = args[3] if len(args) > 3 else None

    url = build_url(first, last, city, state)
    who = " ".join(x for x in [first, last, city, state] if x)
    print(f"🔍 {who}\n   {url}\n")

    try:
        html = fetch(url)
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code} {e.reason}")
        sys.exit(2)
    except Exception as e:
        print(f"❌ fetch failed: {e}")
        sys.exit(2)

    if raw:
        open("/tmp/anywho_raw.html", "w").write(html)
        print("   (raw HTML -> /tmp/anywho_raw.html)\n")

    if is_blocked(html):
        print(f"⛔ blocked / empty response ({len(html)} bytes) — "
              "Cloudflare challenge or no page. Route via CF relay/proxy.")
        sys.exit(3)

    results = parse(html)
    if not results:
        print(f"😶 0 result cards parsed ({len(html)} bytes). "
              "Likely no matches for this name/city/state.")
        return

    print(f"✅ {len(results)} result card(s):\n" + "─" * 60)
    for i, r in enumerate(results, 1):
        hdr = r['name'] or '(name?)'
        if r['age']:
            hdr += f", Age {r['age']}"
        print(f"[{i}] {hdr}")
        if r["lives_in"]:     print(f"    Lives in:     {r['lives_in']}")
        if r["used_to_live"]: print(f"    Used to live: {r['used_to_live']}")
        if r["phones"]:       print(f"    Phones:       {', '.join(r['phones'])}")
        if r["aka"]:          print(f"    AKA:          {r['aka']}")
        if r["related"]:      print(f"    Related:      {r['related']}")
        if r["detail_link"]:  print(f"    Details:      {r['detail_link']}")
        print("─" * 60)

if __name__ == "__main__":
    main()
