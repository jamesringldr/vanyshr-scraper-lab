# Admin Invite Flow — Session Recap

**Date:** 2026-05-16
**Branch:** `dev/admin-flow` (from `sandbox`, NOT pushed, NOT merged)
**Commit:** `f52c174` — `feat: admin invite flow with auth-gated pre-profile`

---

## What shipped

End-to-end admin invite flow per `admin-invite-flow-plan.md`:

- Admin uploads HTML at `/admin/manual-scan`, enters invitee email, clicks **Save & Send Invite**
- `admin-parse-html` saves scan with `status='admin_sent'`, `invited_email`, 7-day TTL
- `admin-send-invite` (new) calls idempotent `create_pending_profile` RPC + `auth.admin.generateLink('magiclink')`
- User clicks magic link → `/auth/callback?profile_id=...&next=/quick-scan/pre-profile/{id}` → `/welcome` (skips `/signup` and BetaModal)
- Pre-profile is auth-gated: anon users see `AdminInviteGate` (masked email, no PII); wrong-account users see sign-out prompt
- RLS on `quick_scans` overhauled: anon SELECT denied on `admin_sent`; authed SELECT requires `invited_email` match or linked profile
- `create_pending_profile` idempotent on `converted_to_user_id`

### Files (9 changed, +1575/-38)

```
A  apps/app/src/components/AdminInviteGate.tsx
M  apps/app/src/pages/admin/manual-scan.tsx
M  apps/app/src/pages/auth/callback.tsx
M  apps/app/src/pages/scan/pre-profile.tsx
A  docs/agent_documentation/duct-tape/admin-invite/admin-invite-test-plan.md
M  supabase/config.toml
M  supabase/functions/admin-parse-html/index.ts
A  supabase/functions/admin-send-invite/index.ts
A  supabase/migrations/20260516_admin_invite_flow.sql
```

### Verified locally

- `pnpm exec tsc --noEmit` → 0 errors
- `pnpm build` → ✓ 9.19s

---

## Current status — where we paused

User deployed edge functions (`admin-parse-html`, `admin-send-invite`). Confirmation of **migration push** (`supabase db push`) was NOT received before the session ended.

Then the user hit:
> `VITE_ADMIN_PARSE_SECRET is not configured` error on admin upload page

**Cause:** Agent E (Wave 2) added a required `x-admin-secret` header to both invite-mode calls. The frontend now needs the env var set; previously it didn't.

**Unresolved question I left with the user:**
- Was `ADMIN_PARSE_SECRET` already set on the deployed Supabase project (from before this branch)?
  - If yes → grab the existing value from Supabase dashboard → Project Settings → Edge Functions → Secrets, paste into `apps/app/.env.local` as `VITE_ADMIN_PARSE_SECRET=...`
  - If no → generate one (`openssl rand -hex 32`), `supabase secrets set ADMIN_PARSE_SECRET=<value>`, AND put same value in `apps/app/.env.local`
- After either path: restart `pnpm dev` (Vite reads env at startup only)

---

## Outstanding before A1–A10 can run

| Item | Status |
|---|---|
| `dev/admin-flow` branch | ✅ committed locally |
| Edge functions deployed | ✅ user confirmed |
| Migration applied (`supabase db push`) | ❓ unconfirmed |
| `ADMIN_PARSE_SECRET` on Supabase | ❓ unconfirmed |
| `VITE_ADMIN_PARSE_SECRET` in `apps/app/.env.local` | ❌ missing (this is the blocker user saw) |
| `SITE_URL` env on Supabase | ❓ unconfirmed (edge function falls back to request `origin` header so likely fine) |
| Supabase Auth → URL Configuration redirect allowlist includes `{SITE_URL}/auth/callback` | ❓ unconfirmed |

---

## Acceptance test status (from final report)

| # | Status | Notes |
|---|---|---|
| A1 | BLOCKED-deploy | Needs migration + secret + browser upload |
| A2 | BLOCKED-deploy | Render branch exists; needs incognito visual check |
| A3 | BLOCKED-deploy | RLS policy in migration; needs anon client test |
| A4 | BLOCKED-deploy | Code path complete; needs UI invocation |
| A5 | BLOCKED-deploy | Needs real email click |
| A6 | PASS (code-only) | Verified via code read |
| A7 | PASS (regression) | Welcome chain untouched |
| A8 | PASS (regression) | Non-admin paths additive-only; `pnpm build` green |
| A9 | PASS (code-only) | Idempotency guard in migration §6 |
| A10 | BLOCKED-deploy | Needs real pre-existing Supabase user |

Full test plan: `admin-invite-test-plan.md` (same folder).

---

## Next actions when user returns

1. **Resolve the env var blocker:**
   - Decide whether to reuse existing `ADMIN_PARSE_SECRET` or generate new
   - Set in Supabase secrets + `apps/app/.env.local` (same value)
   - Restart `pnpm dev`

2. **If migration not yet applied:**
   ```bash
   supabase db push
   ```

3. **Optional autonomous checks I offered to run** (still on the table when you're back):
   - Use Supabase MCP to verify migration applied (CHECK constraint, RLS policies, index)
   - Seed an `admin_sent` row + invoke `admin-send-invite` server-side to confirm A4 mechanics
   - Run anon SQL to confirm A3 (RLS denies anon SELECT on `admin_sent`)
   - Call `create_pending_profile` twice to confirm A9

   To start I just need: Supabase **project ref**.

4. **Walk the browser-side tests** (A1, A2, A5, A6, A7, A8, A10) per `admin-invite-test-plan.md` §2.

---

## Out-of-scope WIP left in working tree (uncommitted)

These were already in your tree at session start and I deliberately did NOT commit them:

- `M supabase/functions/_shared/scraper-lab-client.ts`
- `M supabase/functions/universal-search/index.ts`
- `?? docs/SCRAPER_LAB_DUCT_TAPE.md`

They live on the `dev/admin-flow` branch as uncommitted changes. Handle separately.

---

## Deviation log

- **Branch name:** used `dev/admin-flow` per your direction; orchestrator prompt said `dev/admin-invite-flow`.
- **Plan path:** orchestrator prompt referenced `docs/agent_documentation/admin-invite-flow-plan.md`; actual path is `docs/agent_documentation/duct-tape/admin-invite/admin-invite-flow-plan.md`. Read from actual path.
- **Test plan length:** asked for ~300 lines, came in at ~550. Well-sectioned but verbose.
- **Agent D + E partial completions:** both Haiku agents stopped short on the final UI/render edits citing permission issues. I (Opus) finished them directly in the orchestrator session.
