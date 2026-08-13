# LeakCheck fixtures

Real responses from the free, no-key endpoint:

    https://leakcheck.io/api/public?check=<email>

| fixture | case |
|---|---|
| `found.json` | 8 breaches (jaoehring@gmail.com) |
| `found_yahoo.json` | 8 breaches, different field set (rickioehring@yahoo.com) |
| `not_found.json` | no records (ja_studly@hotmail.com) |
| `invalid.json` | malformed address -- returns the same body as not-found |
| `rate_limited.json` | quota exceeded |

## Things this API does that will bite a naive client

**HTTP status is always 200.** Not-found, invalid input and rate limiting all
return 200, so the status code cannot be used to detect failure. The body has
to be inspected.

**The rate-limit body is not valid JSON.** It uses Python's `False` rather than
JSON's `false`, so `json.loads()` raises on it -- precisely when the service is
under load:

    {"success": False, "error": "Too many requests, you have been ratelimited"}
    {"success": false, "error": "Not found"}          <- valid, for comparison

`rate_limited.json` is transcribed from a response observed three times during
capture, not written from a fresh call: the quota is a time window, and once it
had reset a burst of 14 calls would not reproduce it. The body is byte-for-byte
what the API returned.

**A User-Agent is required.** Requests without a browser-like User-Agent get
403 Forbidden from Cloudflare -- curl succeeds where bare urllib does not.

**Invalid addresses are indistinguishable from misses.** Both return
`{"success": false, "error": "Not found"}`, so validate before calling if the
difference matters.

**`fields` is a union across every breach**, not per-source. The response says a
password leaked somewhere among the listed sources, never which one.

## Re-capturing

Space calls out; the quota is roughly ten per window:

    curl -s -H "User-Agent: Mozilla/5.0 ..." \
      "https://leakcheck.io/api/public?check=<email>"
