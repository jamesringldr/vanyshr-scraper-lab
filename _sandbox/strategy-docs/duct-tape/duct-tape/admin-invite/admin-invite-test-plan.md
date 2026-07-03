# Admin Invite Flow — Manual QA Test Plan

**Branch:** `dev/admin-flow`  
**Spec:** `admin-invite-flow-plan.md` (sections 2, 7, 9, 11)  
**Test environment:** Local dev + Supabase sandbox project  
**Harness type:** Manual (no automated suite)

---

## 1. Pre-flight Setup Checklist

### 1.1 Environment Variables

**`apps/app/.env.local`** (create if missing):
```
VITE_SUPABASE_URL=<placeholder-supabase-url>
VITE_SUPABASE_ANON_KEY=<placeholder-anon-key>
VITE_ADMIN_PARSE_SECRET=<same-secret-as-supabase-env>
```

**Supabase secrets** (Project Settings → API → Secret Management):
- `ADMIN_PARSE_SECRET` — matches `VITE_ADMIN_PARSE_SECRET` in app env
- `SUPABASE_SERVICE_ROLE_KEY` — for edge function RPC calls
- `SITE_URL` — set to local dev origin (`http://localhost:5173`) for local testing, Vercel preview URL for CI

### 1.2 Supabase Auth Configuration

Navigate to **Authentication → URL Configuration**:
1. Add `http://localhost:5173/auth/callback` to Redirect URLs (local dev)
2. Add `https://<preview-branch>.vercel.app/auth/callback` to Redirect URLs (Vercel preview)
3. Add `https://app.vanyshr.com/auth/callback` to Redirect URLs (production)

### 1.3 Database Migration

Apply migration from repo root:

```bash
supabase db push
```

Verify locally:
```bash
supabase db reset  # if working against local stack
```

Or use Supabase dashboard → SQL Editor to run verification queries from section 6 below.

### 1.4 Edge Functions Deploy

```bash
supabase functions deploy admin-parse-html admin-send-invite
```

Verify in Supabase dashboard → Edge Functions → both should show as deployed with status green.

### 1.5 Local Dev Server

From repo root:
```bash
cd apps/app && pnpm dev
```

Confirm terminal shows: `Local: http://localhost:5173`

---

## 2. Acceptance Tests (A1–A10)

### A1: Admin parses HTML + saves with invite_mode

**Steps:**
1. Open `http://localhost:5173/admin/manual-scan` (dev-only route).
2. Select an HTML file (paste Zabasearch/AnyWho search results).
3. Enter recipient email: `test-user@example.com`.
4. Check "Invite-only scan" (should be default).
5. Click "Save & Send Invite".

**Expected:**
- Response includes `success: true`, `scan_id`, `profile_id`.
- Response includes `requires_auth: true` flag.

**Pass criteria:**
- No error toast. Page shows "Invite sent to test-user@example.com".

**DB verification:**
```sql
SELECT id, status, invited_email, profile_data IS NOT NULL AS has_data
FROM quick_scans
WHERE invited_email = 'test-user@example.com'
ORDER BY created_at DESC LIMIT 1;
-- Expected: status='admin_sent', invited_email set, has_data=true
```

---

### A2: Unauthenticated user opens /quick-scan/pre-profile/<admin_sent id>

**Steps:**
1. In normal browser window, navigate to pre-profile URL from A1 response.
2. Should NOT see full profile data (names, phones, addresses, etc.).

**Expected:**
- `<AdminInviteGate />` component renders with message "Your privacy report is ready".
- Shows masked email hint: `tes****@example.com`.
- Button: "Resend link" (disabled for 60s after first send).
- NO exposure data visible.

**Pass criteria:**
- Page source contains no phones, addresses, or relative names.
- Network tab shows no JSON response with `profile_data` key.

---

### A3: Anon Supabase client .select() on admin_sent returns 0 rows (RLS deny)

**Steps:**
1. In browser console, run:
```javascript
const { data, error } = await supabase
  .from('quick_scans')
  .select('*')
  .eq('id', '<scan_id_from_A1>');
console.log(data, error);
```

**Expected:**
- `data` is null or empty array.
- `error` may contain "RLS violation" or similar, OR silently returns 0 rows.

**Pass criteria:**
- Anon user does NOT see the admin_sent scan or its `profile_data`.

---

### A4: Admin clicks "Send invite" → OTP sent, pending_profile created

**Steps:**
1. From `/admin/manual-scan`, enter the scan_id from A1 and click "Send invite" again.
2. Should show success toast without creating duplicate profile.

**Expected:**
- Response: `success: true`, `profile_id: <same_as_A1>`, `existing: true`.
- No duplicate `user_profiles` rows created.

**Pass criteria:**
- Second send succeeds with `existing: true` flag.
- Email deliverability: check test email inbox (Supabase sends via configured auth mail provider).

**DB verification:**
```sql
SELECT COUNT(*) AS profile_count
FROM user_profiles
WHERE id = '<profile_id_from_A1>';
-- Expected: 1 row (not 2)
```

---

### A5: User clicks magic link → authenticated, pre-profile visible

**Steps:**
1. Check email inbox for OTP link sent in A4.
2. Click magic link in email.
3. Should land on `/auth/callback` then redirect to pre-profile.

**Expected:**
- Auth callback completes, session established.
- Browser now shows full pre-profile with names, phones, addresses, age.
- URL remains `/quick-scan/pre-profile/<scan_id>`.

**Pass criteria:**
- `supabase.auth.getSession()` returns `session.user.email = 'test-user@example.com'`.
- Profile data renders without 401 or RLS errors.

---

### A6: Authenticated user clicks "Start Vanyshing" → goes to /welcome, NOT /signup

**Steps:**
1. While authenticated, on pre-profile page, click "Start Vanyshing" button.

**Expected:**
- Routes to `/welcome`.
- NO BetaModal shown.
- NO `/signup` page rendered.

**Pass criteria:**
- URL changes to `/welcome`.
- Page title or header confirms welcome screen, not signup.

---

### A7: User completes welcome flow → normal onboarding

**Steps:**
1. On `/welcome`, proceed through onboarding (Primary Info, etc.).

**Expected:**
- Normal flow: `/onboarding/primary-info` → address selection → completion.

**Pass criteria:**
- No broken routes. User ends at dashboard or post-onboarding screen.

---

### A8: Public QuickScan pre-profile (status=completed) still works without auth

**Steps:**
1. In INCOGNITO window (fresh, no cookies), open public quick-scan flow.
2. Run a full public quick-scan without admin involvement.
3. Click "View Results" or navigate to `/quick-scan/pre-profile/<public_scan_id>`.

**Expected:**
- Pre-profile loads with full data WITHOUT requiring login.
- BetaModal gates "Start Vanyshing" button (existing behavior).

**Pass criteria:**
- Public scan unaffected by admin invite changes.
- BetaModal still shows for public users.

---

### A9: Admin re-sends invite for same scan → idempotent

**Steps:**
1. From A1, call `/admin/manual-scan` with same scan_id.
2. Call "Send invite" a third time.

**Expected:**
- Response: `success: true`, `profile_id: <same>`, `existing: true`.
- `user_profiles` count for that profile remains 1.
- No new sessions or auth links created.

**Pass criteria:**
- Idempotency verified in A4 DB query; re-test here to confirm no regression.

---

### A10: User with existing Supabase account clicks invite link

**Steps:**
1. Create a different Supabase user account (sign up normally if flow exists, or use admin API).
2. Admin sends invite for a new scan to that user's email.
3. Click magic link from email.

**Expected:**
- Magic link includes `profile_id` and `next` query params.
- Callback routes correctly to pre-profile even if user already exists in auth.
- Pre-profile loads with correct profile data (no wrong-account dead-end).

**Pass criteria:**
- No "Wrong Email?" error.
- Session email matches invite email (case-insensitive).
- Pre-profile shows correct PII for the invited scan.

---

## 3. PII Leak Test (Incognito / Private Window)

**Goal:** Verify no profile data leaked to unauthenticated user before magic link.

### Steps

1. **Open incognito/private window.** Clear all cookies.
2. **Visit pre-profile URL** from A1 BEFORE clicking magic link: `http://localhost:5173/quick-scan/pre-profile/<admin_sent_scan_id>`.
3. **Inspect browser DevTools → Network tab.** Refresh page if needed.
4. **Search network requests** for any JSON responses containing:
   - Phone numbers
   - Full addresses
   - Names (beyond masked hint)
   - Relative names
5. **Check page source** (Ctrl+U / Cmd+U): should contain NO phone/address data.
6. **Test RLS in console:**
```javascript
const { data: scans, error } = await supabase
  .from('quick_scans')
  .select('profile_data')
  .eq('id', '<admin_sent_scan_id>');
console.log('Anon sees:', scans); // Must be null/0 rows
```

### Expected Results

- No PII visible on page.
- Network tab shows NO `profile_data` object in responses.
- RLS query returns 0 rows or error.
- AdminInviteGate component only shows masked email hint.

### Pass Criteria

- All three sources (page, network, RLS test) confirm NO anon access to PII.
- Only authenticated users with matching email can see full data.

---

## 4. curl Reference

### admin-parse-html (invite mode)

**Local dev:**
```bash
curl -X POST http://localhost:54321/functions/v1/admin-parse-html \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: <VITE_ADMIN_PARSE_SECRET>" \
  -d '{
    "html": "<html>...</html>",
    "site_name": "zabasearch",
    "page_type": "detail",
    "search_input": {
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com"
    },
    "invite_mode": true,
    "invited_email": "john@example.com",
    "save_to_db": true
  }'
```

**Response (success):**
```json
{
  "success": true,
  "scan_id": "uuid-here",
  "profile_id": "uuid-here",
  "profile_data": { ... },
  "requires_auth": true
}
```

### admin-send-invite (success)

**Local dev:**
```bash
curl -X POST http://localhost:54321/functions/v1/admin-send-invite \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: <VITE_ADMIN_PARSE_SECRET>" \
  -d '{
    "scan_id": "uuid-from-above",
    "email": "john@example.com"
  }'
```

**Response (success):**
```json
{
  "success": true,
  "profile_id": "uuid-here",
  "message": "Invite sent",
  "existing": false
}
```

### admin-send-invite (auth failure 401)

```bash
curl -X POST http://localhost:54321/functions/v1/admin-send-invite \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: wrong-secret" \
  -d '{
    "scan_id": "uuid-from-above",
    "email": "john@example.com"
  }'
```

**Response (401):**
```json
{
  "success": false,
  "error": "Unauthorized"
}
```

### Manual RPC test (idempotency)

In Supabase SQL Editor:
```sql
-- First call: creates profile
SELECT create_pending_profile('<scan_id>', 'user@example.com');
-- Response: {"success":true,"profile_id":"<uuid>","scan_id":"<scan_id>"}

-- Second call: same scan, same email — must return existing=true
SELECT create_pending_profile('<scan_id>', 'user@example.com');
-- Response: {"success":true,"profile_id":"<same-uuid>","scan_id":"<scan_id>","existing":true}
```

---

## 5. Regression Suite (Public Quick-Scan)

**Goal:** Verify existing public quick-scan flow still works.

### Steps

1. Open `http://localhost:5173` (home page).
2. Enter test name/email → initiate public quick-scan.
3. Run search, select candidate profile.
4. Navigate to `/quick-scan/pre-profile/<scan_id>`.
5. See BetaModal gating "Start Vanyshing" button.
6. Complete BetaModal flow (if applicable).
7. Click "Start Vanyshing" → should go to `/signup` (NOT `/welcome`).
8. Sign up normally → verify onboarding path unchanged.

### Pass Criteria

- A8 passes: public scans still render pre-profile without auth.
- BetaModal still gates public users (not skipped).
- Public users still hit `/signup` (not `/welcome`).
- No regression in public flow.

---

## 6. SQL Snippets for Supabase Dashboard

Run in **Supabase → SQL Editor** to verify schema and RLS.

### Verify CHECK constraint includes admin_sent

```sql
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conname = 'quick_scans_status_check';
-- Expected: constraint must list 'admin_sent' as valid status
```

### Verify admin_invited in signup_status

```sql
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conname = 'user_profiles_signup_status_check';
-- Expected: constraint must include 'admin_invited'
```

### Verify RLS policies exist

```sql
SELECT polname, polqual, polroles FROM pg_policy
WHERE polrelid = 'quick_scans'::regclass;
-- Expected policies:
--   - "Public quick scan read" (FOR SELECT TO anon)
--   - "Admin invite scan read" (FOR SELECT TO authenticated)
--   - Existing insert/update policies for non-admin rows
```

### List all admin_sent scans (audit)

```sql
SELECT id, invited_email, invited_at, converted_to_user_id, status
FROM quick_scans
WHERE status = 'admin_sent'
ORDER BY created_at DESC
LIMIT 20;
-- Use for QA tracking: scan_id, recipient email, invite timestamp, profile link status
```

### Find pending_signup scans

```sql
SELECT id, invited_email, converted_to_user_id, created_at
FROM quick_scans
WHERE status = 'pending_signup'
ORDER BY created_at DESC
LIMIT 10;
-- Scans that have been invited but not yet converted to active user
```

---

## 7. Known Gaps / Out-of-Scope (v1)

1. **No client-side resend invite UI** — Admin must re-run `/admin/manual-scan` to resend.
2. **No production admin RBAC** — `DevOnly` wrapper still gates `/admin/manual-scan`; no role-based access control yet.
3. **No automated test suite** — This document IS the manual harness; no CI/CD tests included.
4. **No drip campaigns** — No auto-retry for abandoned invites; no scheduled reminders.
5. **No invite expiry UI** — 7-day TTL is enforced at DB level but no user-facing message on expired invite.

---

## 8. Test Evidence Checklist

Before declaring QA complete, gather:

- [ ] A1–A10 all pass with screenshots/logs.
- [ ] PII leak test (section 3) confirms no anon access.
- [ ] Regression suite (section 5) passes; public quick-scan unchanged.
- [ ] All SQL snippets (section 6) return expected results.
- [ ] curl examples (section 4) execute without errors.
- [ ] No console errors in DevTools while testing authenticated paths.
- [ ] Pre-profile renders for both public (A8) and invite (A2→A5) flows.

---

## 9. Troubleshooting

### "Invite sent" button does nothing
- Check `VITE_ADMIN_PARSE_SECRET` matches `ADMIN_PARSE_SECRET` in Supabase.
- Verify edge functions deployed: `supabase functions list`.
- Check function logs: Supabase dashboard → Edge Functions → click function → Logs tab.

### Magic link redirects to 404
- Verify `SITE_URL` in Supabase env matches local origin (`http://localhost:5173`).
- Confirm `/auth/callback` is in Supabase Auth → URL Configuration → Redirect URLs.
- Check browser Network tab for redirect chain.

### "Wrong Email?" error on pre-profile
- Verify `invited_email` in DB matches session.user.email (case-insensitive).
- Check JWT in Supabase dashboard → Authentication → User Details for invited user.
- Test with console: `supabase.auth.getSession()` to confirm email.

### RLS denies authenticated user reading admin_sent row
- Verify user was created via magic link with `profile_id` passed correctly.
- Check quick_scans.invited_email matches session.user.email exactly (case).
- Run RLS policy query manually with real user email to debug.

### BetaModal still shows for invited user
- Verify `signup_status = 'admin_invited'` was set (or branch logic in pre-profile).
- Check pre-profile component reads `status` field correctly.
- Confirm migration applied: `signup_status` CHECK includes `'admin_invited'`.

---

## 10. Quick Reference

| Component | File | Test |
|-----------|------|------|
| Admin manual scan UI | `apps/app/src/pages/admin/manual-scan.tsx` | A1 |
| Admin invite gate | `apps/app/src/components/AdminInviteGate.tsx` | A2–A3 |
| Pre-profile gate logic | `apps/app/src/pages/scan/pre-profile.tsx` | A5–A6 |
| Auth callback with next | `apps/app/src/pages/auth/callback.tsx` | A5 |
| Parse HTML edge | `supabase/functions/admin-parse-html/index.ts` | A1, curl |
| Send invite edge | `supabase/functions/admin-send-invite/index.ts` | A4, curl |
| RLS policies | `supabase/migrations/20260516_admin_invite_flow.sql` | A3, sec. 6 |
| create_pending_profile | `supabase/migrations/20260516_admin_invite_flow.sql` | A4, A9 |

