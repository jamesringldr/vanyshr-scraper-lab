I have completed a comprehensive review of the codebase and recent changes (last 48 hours) to diagnose the instabilities you

reported.

Executive Summary

The primary instability was caused by a

logic regression

in the latest migration (

20260318_beta_access.sql

). This migration

re-defined a core database function using an outdated signature and logic, which broke the new Beta access funnel and caused

"Edge Function error" crashes. The AnyWho scraper issues were indeed caused by a temporary reversion, but they appear to have

been fixed by a commit yesterday.

---

Identified Issues & Root Causes

1. Edge Function

create-pending-profile

Failure (500 Error)

*

Cause:

The migration

20260318_beta_access.sql

(Section 2) re-defined the SQL function

create_pending_profile(p_scan_id UUID)

with only

one argument

.

*

Conflict:

Previous migrations (

00011

and

20260314

) had updated this function to accept

two arguments

(

p_scan_id

and

p_email

).

*

Result:

The Edge Function calls the RPC with two arguments. Because PostgreSQL supports function overloading, it was likely

calling the

old version

(from

00011

) which still existed in the database.

*

Funnel Breakage:

* The old version sets

signup_status = 'pending_auth'

.

* The new Beta flow (BetaModal) expects

signup_status = 'pending_user'

.

* This caused the

validate_access_code

function to fail silently (updating 0 rows) because its guard clause only allows

updates for

pending_user

profiles.

*

Missing Data:

The

20260318

version of the function is missing critical logic added in

00011

, specifically the

INSERT INTO

user_preferences

call. Without this, the frontend will likely crash later when it tries to load user settings.

2. QuickScan "Bad Request" (400 Error)

*

Cause:

The

ping

warm-up call in

QuickScanForm.tsx

(added recently) might be triggering a 400 error in

universal-search

.

*

Detail:

While the

universal-search

function has a

ping

check, it occurs after

req.json()

is parsed. If the request body is

missing or if the validation for

firstName

/

lastName

triggers unexpectedly due to an empty body in the ping call, it returns a

400 Bad Request

.

*

Recommendation:

Move the

ping

check to the very top and ensure it doesn't trigger name validation.

3. AnyWho Scraper "Reversion"

*

Diagnosis:

You were correct—the scraper parsing logic for blurred phone numbers and addresses was temporarily lost.

*

Status:

Resolved.

Commit

db66adf01df9

yesterday restored the

span[data-content]

parsing logic. My review confirms the current

AnyWhoScraper.ts

correctly handles reconstructed street numbers and phone digits from blurred CSS elements.

---

Suggested Improvements

I recommend the following fixes to stabilize the system (awaiting your approval):

1.

Consolidate

create_pending_profile

RPC:

* Update the function to accept two arguments:

(p_scan_id UUID, p_email TEXT DEFAULT NULL)

.

* Explicitly

DROP

the one-argument version to prevent overloading confusion.

* Ensure it sets

signup_status = 'pending_user'

(to support the Beta funnel).

* Restore the

INSERT INTO user_preferences

and

initcap()

name normalization.

2.

Harden

validate_access_code

and

join_waitlist

:

* These functions currently return

{ success: true }

even if the

UPDATE

affects 0 rows (due to status guards). They should

check

FOUND

(the row count) and return a specific error if the profile isn't in the correct state.

3.

Refine

universal-search

Ping:

* Optimize the ping check to avoid any possibility of 400 errors during the warm-up phase.