# Opus 4.7 Master Prompt — Admin Invite Flow

Copy everything below the line into Claude Code (Opus) as the kickoff message.

---

You are the **lead orchestrator** for the Vanyshr monorepo feature **Admin Invite Flow** (codename: `duct-tape-plan`).

## Source of truth

Read and follow this document **before writing any code**:

`docs/agent_documentation/admin-invite-flow-plan.md`

That file defines architecture, acceptance tests (A1–A10), file checklist, RLS requirements, edge functions, frontend changes, and Haiku sub-agent waves. **Do not improvise alternate designs** unless you hit a blocker — then stop, explain the blocker, and propose the smallest deviation.

Also respect: `CLAUDE.md`, `docs/CICD.md`.

## Your mission

Implement end-to-end:

**Admin manual scan → email invite → magic link → auth-gated pre-profile → Start Vanyshing → `/welcome` (skip beta + `/signup`) → existing onboarding.**

## Hard rules (violations = failure)

1. **Branch:** `dev/admin-invite-flow` from `staging`. Never commit to `main`. Never force-push `main`.
2. **Scope:** Only touch files listed in the plan §10 (+ imports/types they require). No drive-by refactors, no unrelated lint fixes, no new markdown unless the plan says so.
3. **Secrets:** Never commit `.env.local`, real API keys, or `pnpm-lock.yaml`.
4. **Security:** Client-side auth gates are **not sufficient**. `admin_sent` scans must be protected by **RLS** (or an edge function if RLS blocks you — prefer RLS per plan).
5. **Regression:** Public QuickScan pre-profile (`status != 'admin_sent'`) must still work **without** auth (test A8).
6. **Commits:** One final commit when A1–A10 pass (or document which tests are blocked and why). Message format: `feat: admin invite flow with auth-gated pre-profile`
7. **Deploy:** Do not merge to `main`. Do not push unless the user asks.

## Execution model

You are **Opus orchestrator**. Delegate parallel work to **Haiku sub-agents** using the wave structure in plan §8. Each sub-agent prompt must include:

- Exact files to create/modify
- Files they must **not** touch
- Deliverables checklist
- Model: **Haiku**
- Instruction to return a short summary + list of changed files + any blockers

**Do not start Wave 2 until Wave 1 is merged and migration applies locally.**

After each wave, **stop and report** to the user:

- What shipped
- Files changed
- How you verified (command output or manual step)
- Blockers for next wave

## Wave 0 — You (Opus) do this first, alone

```bash
git fetch origin
git checkout staging
git pull origin staging
git checkout -b dev/admin-invite-flow
git branch --show-current   # must print dev/admin-invite-flow
```

1. Read the full plan + skim reference files in plan §15.
2. Grep for latest `create_pending_profile` migration (do not assume `00012` is current).
3. Create migration shell: `supabase/migrations/20260516_admin_invite_flow.sql` with section comments only (Agent A will fill).

**Checkpoint:** Report branch name + confirmation plan was read. Do not proceed to Wave 1 until reported.

---

## Wave 1 — Launch 3 Haiku agents in parallel

### Haiku Agent A — Database

**Prompt template:**

```
You are implementing the database layer for Vanyshr admin invite flow.

READ ONLY context:
- docs/agent_documentation/admin-invite-flow-plan.md sections 4.1–4.4, 11
- supabase/migrations/00003_core_schema.sql (quick_scans RLS)
- supabase/migrations/00005_profile_schema_update.sql (status check)
- Grep latest create_pending_profile definition

OWN: supabase/migrations/20260516_admin_invite_flow.sql (fill in)

DELIVER:
1. status value 'admin_sent' in quick_scans_status_check
2. Columns invited_email, invited_at
3. Replace anon blanket SELECT with public vs admin_sent policies (plan §4.2)
4. create_pending_profile idempotency when converted_to_user_id IS NOT NULL
5. Add signup_status 'admin_invited' to user_profiles CHECK if needed
6. SQL comments with manual verification queries

DO NOT TOUCH: edge functions, apps/app

VERIFY: supabase db reset (or note if CLI unavailable)

Return: summary, files changed, any policy edge cases.
```

### Haiku Agent B — Edge functions

**Prompt template:**

```
You are implementing edge functions for Vanyshr admin invite flow.

READ:
- docs/agent_documentation/admin-invite-flow-plan.md sections 5.1–5.2
- supabase/functions/admin-parse-html/index.ts
- supabase/functions/create-pending-profile/index.ts
- supabase/config.toml (admin-parse-html entry)

OWN:
- MODIFY supabase/functions/admin-parse-html/index.ts (invite_mode, invited_email, admin_sent status, 7d expires_at)
- CREATE supabase/functions/admin-send-invite/index.ts
- MODIFY supabase/config.toml for new function

DELIVER admin-send-invite:
- POST { scan_id, email }
- ADMIN_PARSE_SECRET header (same pattern as parse-html)
- create_pending_profile via service role (idempotent)
- Magic link redirect: /auth/callback?profile_id=X&next=/quick-scan/pre-profile/{scanId}
- Use auth.admin.generateLink or equivalent
- CORS + error handling matching sibling functions

DO NOT TOUCH: migrations, apps/app

Add curl examples in comments.

Return: summary, files changed, env vars needed.
```

### Haiku Agent C — Auth callback

**Prompt template:**

```
You are implementing auth callback redirect for Vanyshr admin invite flow.

READ:
- docs/agent_documentation/admin-invite-flow-plan.md section 6.2
- apps/app/src/pages/auth/callback.tsx

OWN: apps/app/src/pages/auth/callback.tsx (+ types if any)

DELIVER:
- When profile_id present: after link-auth-to-profile, honor ?next= allowlisted to /quick-scan/pre-profile/* only
- Default remains /welcome when no valid next
- Comment redirect matrix at top of file

DO NOT TOUCH: pre-profile, manual-scan, migrations, edge functions

Return: summary, files changed.
```

**After Wave 1:** Merge all changes. Run `supabase db reset` if possible. Fix conflicts yourself. Report checkpoint before Wave 2.

---

## Wave 2 — Launch 2 Haiku agents in parallel (after Wave 1 merged)

### Haiku Agent D — Pre-profile gate

**Prompt template:**

```
You are implementing auth-gated pre-profile for Vanyshr admin invite flow.

READ:
- docs/agent_documentation/admin-invite-flow-plan.md sections 6.3–6.4
- apps/app/src/pages/scan/pre-profile.tsx
- apps/app/src/pages/auth/check-email.tsx (tone reference)

OWN:
- MODIFY apps/app/src/pages/scan/pre-profile.tsx
- CREATE apps/app/src/components/AdminInviteGate.tsx

DELIVER:
1. On load: fetch status, invited_email, converted_to_user_id
2. If status === 'admin_sent' && no session → AdminInviteGate (no profile_data rendered)
3. If session && email mismatch invited_email → wrong account UI + sign out
4. handleStartVanyshing: if session + profile linked → navigate /welcome, skip BetaModal
5. Public flow unchanged for non-admin_sent

DO NOT TOUCH: manual-scan, callback, migrations, edge functions

Return: summary, files changed.
```

### Haiku Agent E — Admin UI

**Prompt template:**

```
You are implementing admin manual scan invite UI for Vanyshr admin invite flow.

READ:
- docs/agent_documentation/admin-invite-flow-plan.md section 6.1
- apps/app/src/pages/admin/manual-scan.tsx
- supabase/functions/admin-parse-html (request shape)

OWN: apps/app/src/pages/admin/manual-scan.tsx

DELIVER:
1. invitedEmail field (required for invite)
2. invite_mode default true
3. "Save & Send Invite" flow: admin-parse-html then admin-send-invite
4. x-admin-secret header from import.meta.env.VITE_ADMIN_PARSE_SECRET
5. Success/error states; hide or gate "Open pre-profile" for invite-only scans

DO NOT TOUCH: pre-profile, callback, migrations

Return: summary, files changed, env vars for .env.local.example if applicable.
```

**After Wave 2:** Merge. Run `cd apps/app && pnpm build`. Report checkpoint.

---

## Wave 3 — Haiku Agent F — Test plan doc

**Prompt template:**

```
Create docs/agent_documentation/admin-invite-test-plan.md from plan section 9 + acceptance tests A1–A10.

Include: step-by-step manual tests, curl for edge functions, Supabase Auth redirect URL checklist, incognito PII leak test.

Do not modify application code.
```

---

## Wave 4 — You (Opus) integrate & verify

1. Resolve any merge conflicts; ensure single migration date/file.
2. `cd apps/app && pnpm build` — must pass.
3. Walk acceptance tests **A1–A10** from the plan. For each: PASS / FAIL / BLOCKED + reason.
4. If RLS untestable locally, document exact SQL to run in Supabase SQL editor.
5. Single commit on `dev/admin-invite-flow`:

```
feat: admin invite flow with auth-gated pre-profile

Admin manual scans can invite users by email; magic link lands on
gated pre-profile then welcome without signup.
```

6. Final report to user:

| Section | Content |
|---------|---------|
| Summary | 3–5 bullets |
| Files changed | List |
| Acceptance tests | A1–A10 table |
| Env setup | Vars + Supabase dashboard steps |
| Deploy commands | `supabase db push`, `supabase functions deploy ...` |
| Known gaps | Anything deferred |

## Blocker protocol

If stuck >15 minutes on one issue:

1. State hypothesis
2. What you tried
3. Smallest fix options (max 2)
4. **Stop** and ask user — do not spiral

## Sub-agent model reminder

All delegated workers: **Haiku**. You (orchestrator): **Opus**.

## Start now

Begin Wave 0. Read `docs/agent_documentation/admin-invite-flow-plan.md` in full, then execute Wave 0 and report before launching Wave 1.
