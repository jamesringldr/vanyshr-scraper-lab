# Code Review Punchlist
> Cross-referenced against codebase — March 20, 2026
> Sources: G Response.md, CU Response.md, CL Response.md

---

## P0 — Production Breaking

### ~~1. `create_pending_profile` (2-arg) writes `pending_auth` instead of `pending_user`~~ ✅ RESOLVED
- **File:** `supabase/migrations/20260314_normalize_profile_on_creation.sql:44`
- **Sources:** G, CU
- **Critical:** Yes
- **Fix:** `supabase/migrations/20260320_fix_pending_profile_status.sql` — `CREATE OR REPLACE` the 2-arg function with `signup_status = 'pending_user'`. Also drops the dead 1-arg overload (see #5). Apply migration to resolve.

---

### ~~2. `validate_access_code` returns `{ success: true }` when profile status UPDATE hits 0 rows — no `FOUND` check~~ ✅ RESOLVED
- **File:** `supabase/migrations/20260318_beta_access.sql:303–313`
- **Sources:** G (implied), confirmed in code
- **Critical:** Yes
- **Fix:** `supabase/migrations/20260320_fix_validate_access_code.sql` — reordered ops (profile update first, use_count increment second) and added `IF NOT FOUND` guard. A profile in the wrong state now returns `{ success: false }` and does not consume a code use.

---

### ~~3. `scanId ?? profile.id` falls back to synthetic `aw-*` IDs when `scan_id` is null~~ ✅ RESOLVED
- **File:** `apps/app/src/pages/scan/quick-scan.tsx:15`
- **Source:** CU
- **Critical:** Yes
- **Fix:** Guard added in `handleSelectProfile` — if `scanId` is null, navigate to `/quickscan-error` with `searchParams` so the user can queue a retry. Removed the `?? profile.id` fallback entirely.

---

## P1 — Important

### ~~4. `validate_access_code` race condition: check and increment are non-atomic~~ ✅ RESOLVED
- **File:** `supabase/migrations/20260318_beta_access.sql:293–301`
- **Source:** CL
- **Critical:** Yes (for limited codes)
- **Fix:** `supabase/migrations/20260320_fix_validate_access_code_atomic.sql` — collapsed check+increment into a single `UPDATE ... WHERE use_count < max_uses RETURNING id`. Reordered ops: claim use atomically first, then advance profile, with use_count compensation rollback if profile update fails.

---

### ~~5. Dead 1-arg `create_pending_profile(UUID)` overload lives alongside the canonical 2-arg version~~ ✅ RESOLVED (bundled with #1)
- **File:** `supabase/migrations/20260318_beta_access.sql:57`
- **Sources:** G, CU
- **Critical:** No
- **Fix:** `supabase/migrations/20260320_fix_pending_profile_status.sql` — `DROP FUNCTION IF EXISTS public.create_pending_profile(UUID)` before the `CREATE OR REPLACE`.

---

### ~~6. `universal-search` ping check is correct in code — console 400s are a deploy skew issue~~ ✅ RESOLVED
- **File:** `supabase/functions/universal-search/index.ts:62–66`
- **Sources:** G, CU
- **Critical:** No
- **Fix:** `packages/ui/src/components/application/quick-scan-form.tsx:162` — added `.catch(() => {})` to the fire-and-forget ping call so deploy-skew 400s don't surface in the console.

---

### 7. No rate limiting on `validate-access-code`
- **File:** `supabase/functions/validate-access-code/index.ts`
- **Source:** CL
- **Critical:** No
- **Notes:** No per-profile or IP throttle. Enumeration of short codes is possible. Low urgency for beta-scale, but should be tracked before growth.

---

### 8. `purge_orphaned_beta_profiles` function exists but no cron is wired
- **File:** `supabase/migrations/20260318_beta_access.sql:395`
- **Source:** CL
- **Critical:** No
- **Notes:** The cleanup function is deployed and correct, but without a Supabase scheduled job it never runs. `pending_user` profiles will accumulate indefinitely.

---

## P2 — Minor / Nit

### ~~9. `join-waitlist` returns HTTP 500 for a business logic / client error~~ ✅ RESOLVED
- **File:** `supabase/functions/join-waitlist/index.ts:47–52`
- **Source:** CL
- **Critical:** No
- **Fix:** Changed `status: 500` → `status: 400` for the `!data?.success` branch.

---

### ~~10. No email format validation in `join-waitlist` Edge Function~~ ✅ RESOLVED
- **File:** `supabase/functions/join-waitlist/index.ts:22–28`
- **Source:** CL
- **Critical:** No
- **Fix:** Added regex format check after presence validation — returns 400 for malformed emails before the RPC is called.

---

### 11. `use_count` not decremented when abandoned `accessed_pending_signup` profiles are purged
- **File:** `supabase/migrations/20260318_beta_access.sql:416–424`
- **Source:** CL
- **Critical:** No
- **Notes:** If a user enters a valid code then never signs up, the purge job deletes the profile but the code's `use_count` stays incremented. For limited codes, abandoned conversions permanently eat into the cap. Intentional or oversight — worth deciding explicitly.

---

### ~~12. Duplicate error string in `BetaModal.tsx`~~ ✅ RESOLVED
- **File:** `apps/app/src/components/BetaModal.tsx:95, 100`
- **Source:** CL
- **Critical:** No
- **Fix:** Extracted to `INVALID_CODE_MSG` constant above the component.

---

## Resolved

### 13. AnyWho scraper regression — phones & blurred addresses
- **Sources:** G, CU
- **Status:** Resolved in commit `db66adf`
- **Notes:** `span[data-content]` phone assembly and blurred street-number parsing restored. Residual risk: CF relay HTML changes can silently re-break parsers without a git revert — no code-level safeguard.

---

## Summary

| # | Issue | Priority | Critical? |
|---|-------|----------|-----------|
| ~~1~~ | ~~`create_pending_profile` 2-arg writes `pending_auth` not `pending_user`~~ | ~~P0~~ | ✅ |
| ~~2~~ | ~~`validate_access_code` returns success with 0 rows updated~~ | ~~P0~~ | ✅ |
| ~~2~~ | ~~`validate_access_code` returns success with 0 rows updated~~ | ~~P0~~ | ✅ |
| ~~3~~ | ~~`scanId ?? profile.id` falls back to `aw-*` synthetic IDs~~ | ~~P0~~ | ✅ |
| ~~4~~ | ~~`validate_access_code` non-atomic check+increment race condition~~ | ~~P1~~ | ✅ |
| ~~5~~ | ~~Dead 1-arg `create_pending_profile` overload~~ | ~~P1~~ | ✅ |
| ~~6~~ | ~~Ping 400s from deploy skew~~ | ~~P1~~ | ✅ |
| 7 | No rate limiting on `validate-access-code` | P1 | No |
| 8 | `purge_orphaned_beta_profiles` cron not wired | P1 | No |
| ~~9~~ | ~~`join-waitlist` returns 500 for business logic error~~ | ~~P2~~ | ✅ |
| ~~10~~ | ~~No email format validation in `join-waitlist`~~ | ~~P2~~ | ✅ |
| 11 | `use_count` not decremented on purge | P2 | No |
| ~~12~~ | ~~Duplicate error string in `BetaModal.tsx`~~ | ~~P2~~ | ✅ |
| 13 | AnyWho scraper regression | — | Resolved |
