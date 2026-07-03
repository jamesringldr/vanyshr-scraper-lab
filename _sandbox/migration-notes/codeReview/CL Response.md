Code Review — Private Beta Access Gate

Scope:

5 commits, 11 files, +1058/-89 lines

Verdict:

💬 Approve with suggestions — one important security note, a few minors ---

Strengths

-

Migration is excellent.

Well-structured, idempotent (

CREATE OR REPLACE

,

DROP TRIGGER IF EXISTS

), thorough comments explaining the funnel states, and the cleanup function is thoughtful. -

RLS is correct.

access_codes

is service_role-only — no client ever touches this table directly. Consistent with the project's pattern. -

create_pending_profile

called

before

the modal

is the right call. Avoids a race where the user submits a code and the profile doesn't exist yet. -

isStarting

guard on the CTA button

prevents double-submissions cleanly. -

State reset in

handleClose

is properly deferred 300ms to avoid flicker mid-animation. ---

Issues

🟡 [important] Race condition in

validate_access_code

—

max_uses

cap

supabase/migrations/20260318_beta_access.sql:293-301

-- Check first

IF v_code.max_uses

IS

NOT

NULL

AND

v_code.use_count >= v_code.max_uses

THEN

RETURN

...;

END

IF;

-- Increment separately

UPDATE access_codes

SET

use_count = use_count +

1

...

WHERE

id = v_code.id; Two simultaneous requests for a

max_uses = 1

code can both pass the check before either increments. For a shared multi-use beta code (unlimited

max_uses

) this is harmless. For user-specific codes (Option B), it's a real double-spend. The fix is to make the check and increment atomic: UPDATE public.access_codes

SET

use_count = use_count +

1

, updated_at = NOW()

WHERE

id = v_code.id

AND

(max_uses

IS

NULL

OR

use_count < max_uses) RETURNING id

INTO

v_updated_id; IF v_updated_id

IS

NULL

THEN

RETURN

jsonb_build_object(

'success'

,

false

,

'error'

,

'Access code has reached its usage limit'

);

END

IF; ---

🟡 [important] No rate limiting on

validate-access-code

supabase/functions/validate-access-code/index.ts

The edge function accepts unlimited attempts from any

profile_id

. A bot could enumerate short codes rapidly. With the current setup there's no IP-based or profile-based throttle. For the beta gate this is low-urgency (codes are presumably hard to guess), but worth tracking before growth. Options: Supabase rate limits at the API gateway level, or a simple attempt counter per profile in the DB. ---

🟢 [nit]

join-waitlist

returns 500 for a 400-class error

supabase/functions/join-waitlist/index.ts:47-51

if

(!data?.success) {

return

new

Response(..., {

status

:

500

, ... });

// "Profile not found or not in pending state"

"Profile not found or not in pending state" is a client/business logic failure, not a server error. Should be

status: 400

. Same pattern exists but handled better in

validate-access-code

which returns 200 with

success: false

. ---

🟢 [nit] Duplicate error string in

BetaModal.tsx

apps/app/src/components/BetaModal.tsx:95,100

The access code error message appears verbatim in two places. Extract to a constant at the top of the function:

const

INVALID_CODE_MSG =

"Invalid code — please check your code and retry, or sign up for the waitlist and we'll send you a valid

code soon."

; ---

🟢 [nit] No email format validation in

join-waitlist

supabase/functions/join-waitlist/index.ts:24

The edge function validates presence but not format. The client's

type="email"

and

required

attributes handle this in practice, but a direct API call could store a malformed email. The DB just does

LOWER(TRIM(...))

with no format check. Worth adding a simple regex check in the edge function since this email is the user's waitlist contact. ---

Questions

❓ The

purge_orphaned_beta_profiles

function is wired to be called by a scheduled cron job — is that cron job set up in Supabase, or is it pending? The function exists but won't run until it's scheduled. Worth tracking so orphaned

pending_user

profiles don't accumulate indefinitely. ❓ When a user with

accessed_pending_signup

status is purged (entered a code, never signed up), the

use_count

on their code is

not

decremented. For limited codes this means abandoned conversions eat into the cap. Is that intentional?