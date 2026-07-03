Here is a concise diagnosis from the git history on `sandbox` in the last ~48 hours (Mar 18–20, 2026) plus the code paths those commits touch.

---

## Timeline (what actually changed)

|When (log)|Commit|What it did|
|---|---|---|
|Wed Mar 18|`126503d`|Beta gate: `BetaModal`, `validate-access-code` / `join-waitlist` functions, migration `20260318_beta_access.sql`. Pre-profile “Start Vanyshing” now calls `create-pending-profile` before opening the modal (instead of only storing `pendingScanId` and navigating to `/signup`).|
|Thu Mar 19 AM|`5626aff`|Quick Scan UI only: headline, subcopy, chip, privacy bullet order/size — no changes to `invoke`, zip logic, or scan flow.|
|Thu Mar 19|`972a288`|Root route `/` → `/quick-scan` (`App.tsx`).|
|Thu Mar 19|`db66adf`|AnyWho scraper: restore `span[data-content]` phone assembly and blurred street-number handling (explicitly described as fixing breakage from the CF Worker relay work).|

Commits before that window but directly tied to your symptoms (Mar 16):

- `a96f690`: CF Worker relay for AnyWho, `universal-search` `{ ping: true }` warm-up, client retry + `scraper_failed`, quickscan error page / `queue-scan-retry`.
- `79db6c1`: Zip validated in-browser (Zippopotam), `quick_scans` row created inside `universal-search` when no `scan_id` is sent (no zip-lookup round-trip on submit).

So: the scraper regression you saw was not from “yesterday’s UI copy” commit; it lines up with relay + HTML parsing, and the repo itself documents that in `db66adf`.

---

## 1. “Universal scraper reverted” / phones & blurred addresses

What happened (in repo terms): This reads as parser drift after the CF relay path, not a literal git revert of `AnyWhoScraper.ts` to an ancient revision.

- Relay/proxy HTML can differ slightly from what the DOM parsers assumed.
- `db66adf` switches phone extraction back to the split-span + `data-content` model and adjusts address logic so house numbers hidden via blur / pseudo-elements still reconstruct correctly — matching what you described as “we fixed this over a week ago then it came back.”

Did `5626aff` cause it? No. That diff is only marketing/layout in `quick-scan-form.tsx` (e.g. “Are you exposed?”, chip, bullet text). It does not touch Edge Functions or scrapers.

Stability after `db66adf`: In code, the AnyWho-specific issues you named are directly addressed by that commit, _assuming_ `universal-search` (and shared scraper code) is deployed to the same project the app calls. If production/preview still runs an older function bundle, you would still see the old behavior.

Residual risk: Any future change to relay HTML, CF env (`CF_RELAY_URL` / `CF_RELAY_TOKEN`), or fallback proxies can break parsers again without any “revert” in git.

---

## 2. Quick Scan “Bad Request” / console noise

Relevant client behavior (unchanged by `5626aff`):

quick-scan-form.tsxLines 160-163

// Warm up universal-search on mount so it's hot by the time the user submits

useEffect(() => {

supabaseClient.functions.invoke("universal-search", { body: { ping: true } });

}, [supabaseClient]);

Server behavior:

index.tsLines 61-72

// Warm-up ping — keeps the function hot, no DB writes, no scraping

if ((requestBody as any).ping === true) {

return new Response(JSON.stringify({ pong: true }), {

status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' }

});

}

if (!firstName || !lastName) {

return new Response(

JSON.stringify({ error: 'firstName and lastName are required' }),

{ status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }

Likely cause of `400 Bad Request` on every visit: The browser build includes the ping, but the deployed `universal-search` is older and has no `ping` branch. Then the request body is only `{ ping: true }`, `firstName` / `lastName` are missing → 400. The Supabase client often surfaces that as a non-2xx / “Bad Request” style error in the console even though the real scan (with names) might still work.

Other causes to keep in mind: malformed JSON, wrong project URL/key, or a failed OPTIONS/CORS path (less common for `functions.invoke`).

So: Quick Scan “stability” from yesterday’s UI commit is unrelated; warm-up + deploy skew is the main hypothesis for persistent console errors.

---

## 3. Pre-profile “Start Vanyshing” → Edge Function non-2xx

What changed: `126503d` replaced “navigate to signup and create profile later” with an immediate `create-pending-profile` call:

pre-profile.tsxLines 487-517

const handleStartVanyshing = useCallback(async () => {

if (!scanId) {

setStartError("Scan ID is missing. Please go back and try again.");

return;

}

// ...

const { data, error } = await supabase.functions.invoke<{

success: boolean;

profile_id?: string;

scan_id?: string;

error?: string;

}>("create-pending-profile", {

body: { scan_id: scanId },

});

The Edge Function then RPCs `create_pending_profile` with `p_scan_id` / `p_email`.

Failure buckets:

1. `create-pending-profile` or RPC not deployed on the environment you’re hitting → non-2xx or opaque client error.
2. DB migration not applied (e.g. `create_pending_profile` missing or wrong) → RPC error → 500 from the function.
3. Wrong `scanId` in the URL (see below) → “Quick scan not found” or invalid UUID handling → 500 or client-side error parsing.

Important bug-shaped issue (pre-existing relative to beta, but now much more visible): Quick Scan navigation does:

quick-scan.tsxLines 12-15

navigate(`/quick-scan/pre-profile/${scanId ?? profile.id}`);

AnyWho list rows use synthetic ids like `aw-${index}` (not `quick_scans` UUIDs). If `scan_id` from `universal-search` is null (e.g. `quick_scans` insert failed but search still returned profiles), the app sends users to `/quick-scan/pre-profile/aw-0` (etc.). That is not a valid `quick_scans.id`, so `create_pending_profile` cannot find the row — exactly the kind of failure you’d only notice after “Start Vanyshing” started calling the Edge Function on every click.

So the beta flow didn’t invent the bad id, but it surfaces it as a hard Edge Function failure instead of deferring to signup.

Note on migrations: `20260318_beta_access.sql` adds a second overload `create_pending_profile(p_scan_id UUID)` while the Edge Function still calls the two-argument RPC (`p_scan_id`, `p_email`). PostgreSQL keeps both overloads unless one is dropped; the Edge path should still hit `(uuid, text)` from `00012`, but having two live definitions is easy to get wrong on future edits — worth consolidating when you’re allowed to change code.

---

## 4. Summary: what caused the “recent instability”

|Symptom|Most plausible repo-backed cause|
|---|---|
|Phones / blurred addresses “regressed”|`a96f690` relay + HTML; fixed in `db66adf`. Not the Mar 19 UI-only commit.|
|Quick Scan console 400 / bad request|`universal-search` ping (`a96f690`) vs stale deployed function without `ping` → 400 on mount.|
|Start Vanyshing non-2xx|`126503d` now requires `create-pending-profile` + valid `quick_scans` UUID; `scanId ?? profile.id` can put `aw-*` in the URL; plus deploy/DB parity.|

---

## 5. Suggested improvements (for you to approve later — no changes made here)

1. Deploy parity: Deploy `universal-search` (with `ping`) and `create-pending-profile` together with the app build you test; confirm preview vs production.
2. Never use `profile.id` as `scanId`: Only navigate to pre-profile with a real `quick_scans` id; if `scan_id` is missing, block with a clear error or retry creating the row instead of substituting `aw-0`.
3. Warm-up error handling: Optionally ignore / catch non-2xx from ping in the client, or gate ping on a feature flag, after you’re sure production returns `200` for `{ ping: true }`.
4. RPC hygiene: Merge `create_pending_profile` overloads into a single canonical `(uuid, text)` implementation that includes beta `signup_status` behavior, so the next migration can’t silently fork behavior.
5. Observability: Log correlation id (`scan_id`) in `universal-search` when insert fails so you can see `scan_id: null` responses in Supabase logs.

---

Bottom line: Yesterday’s Quick Scan copy commit (`5626aff`) did not break scrapers or Edge Functions. The instability lines up with (1) CF relay + parser mismatch, fixed in `db66adf`, (2) ping vs deploy skew for console 400s, and (3) the beta pre-profile change exposing invalid or missing `scan_id` when navigating with `scanId ?? profile.id`. I did not modify any files per your request.