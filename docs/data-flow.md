# Data flow — scrapers to database

Where every field a scraper produces ends up, and which fields currently have
nowhere queryable to go.

Scraper models are in this repo (`data_models.py`, `targets/*/models.py`).
Destination tables are in `Vanyshr-mono` (`docs/schema.md`,
`supabase/migrations/`). Field lists below were generated from the code and
migrations rather than transcribed.

**The distinction that matters throughout:** a field is either a *first-class
column* you can filter, join and index on, or it is *inside a JSONB blob*,
where it survives but cannot be queried. Almost nothing is genuinely homeless —
`data_snapshot`, `full_data` and `full_profile_results` will swallow anything.
The question is always which of the two a field lands in, and whether that was
a decision or an accident.

---

## The pipeline

```
  user input
      │
      ▼
  quick_scans ──────────────────────── the search itself
      │
      ▼
  Phase 1: 4 brokers in parallel (~2.1s, ~$0.004)
      │
      ├─► scrape_results ───────────── per-broker raw call record
      │
      ▼
  dedup / grouping
      │
      ▼
  quickscan_dedup_groups ───────────── candidates shown for selection
      │
      ▼
  USER SELECTS THEIR PROFILE
      │
      ▼
  Phase 2: full profiles + enrichment
      │
      ├─► scrape_results ───────────── full profile calls
      ├─► quickscan_enrichment ─────── holehe + leakcheck
      │
      ▼
  exposures ────────────────────────── one row per broker record, tracked over time
      │
      ▼
  ONBOARDING: user approves / denies each datapoint
      │
      ▼
  user_emails / user_phones / user_addresses / user_aliases
                                        the monitoring criteria
```

---

## Stage 1 — the search

`quick_scans` holds `search_input`, `session_id`, `status`, `profile_matches`,
`candidate_matches`, `selected_match_id`, `data_sources`, `scraper_runs`,
`expires_at`, `converted_to_user_id`.

This already covers anonymous-to-authenticated conversion and which candidate
the user picked. No changes needed.

---

## Stage 2 — Phase 1 summary results

Every broker is normalised into the shared `data_models.SummaryResult` by
`sequence_runner._scrape_broker`. The brokers disagree on field names, which is
why that mapping layer exists and is contract-tested.

| shared field | fps | npd | anywho | zaba |
|---|---|---|---|---|
| `full_name` | `fullName` | `fullName` | `fullName` | `fullName` |
| `result_id` | `resultId` | `resultId` | `resultId` | `resultId` |
| `address` | `address` | `addressPreview` | `address` | `address` |
| `age` | `age` (int) | — | — | `age` (int) |
| `age_range` | — | `ageRange` | `ageRange` | — |
| `phone` | `phone` | `phonePreview` | `phone` | `phone` |
| `email` | `email` | `email` | `email` | `email` |
| `aliases` | `aliases` | `aliases` | `aliases` | `aliases` |
| `relatives` | `relatives` | `relatives` | `relatives` | `relatives` |
| `profile_url` | `profileUrl` | `profileUrl` | `profileUrl` | `profileUrl` |

**Destination:** `quickscan_dedup_groups`

| what | column | queryable |
|---|---|---|
| every member summary, in full | `full_data` JSONB | no |
| group key | `dedup_id` | yes |
| ranking | `rank`, `average_confidence` | yes |
| which brokers contributed | `sources TEXT[]` | yes |
| display name | `primary_name` | yes |
| **derived** age | `primary_age` | yes — see caution below |
| **derived** location | `primary_city`, `primary_state` | yes |
| conflict flags | `age_conflict`, `age_note` | yes |

Per-broker call records go to `scrape_results`: `input_data`,
`summary_results`, `full_profile_results`, `status`, `response_time_ms`,
`response_bytes`.

### Caution: the `primary_*` columns are caches, not truth

`primary_age` is the median across group members. On the `oehring` record the
members are **61, 62, 37, 37**, so it stores 61 — a value no source asserts and
which we know to be wrong. `primary_city` has the same problem: three brokers
say Cameron, AnyWho says Kansas City.

Nothing is lost — `full_data` keeps every member — but a consumer reading
`primary_age` gets a number that looks authoritative and isn't.

**Convention to adopt:** `primary_*` exists for ranking and list display only.
Anything user-facing that states a value should read the members and show the
disagreement. That matches the product intent — showing what brokers publish,
including that they contradict each other.

---

## Stage 3 — full profiles

Each broker has its own `Profile` model. They overlap but are not identical.

| field | fps | npd | anywho | zaba |
|---|:--:|:--:|:--:|:--:|
| `profileId` | ✓ | ✓ | ✓ | ✓ |
| `fullName` | ✓ | ✓ | ✓ | ✓ |
| `age` | ✓ | ✓ | ✓ | ✓ |
| `dateOfBirth` | | ✓ | | |
| `currentAddress` | ✓ | ✓ | ✓ | ✓ |
| `previousAddresses` | ✓ | ✓ | ✓ | ✓ (`pastAddresses`) |
| `phoneNumbers` | ✓ | ✓ | ✓ | ✓ |
| `emailAddresses` | ✓ | ✓ | ✓ | ✓ |
| relatives | ✓ | ✓ | ✓ (`familyMembers`) | ✓ |
| `associates` | ✓ | | | ✓ |
| `properties` | ✓ | ✓ | ✓ | ✓ |
| `aliases` | | | | ✓ |

**Destination:** `scrape_results.full_profile_results` (JSONB), then one
`exposures` row per broker record.

`exposures` is the right shape for this and already carries what removal
verification needs:

| need | column |
|---|---|
| identity of this specific broker record | `profile_identifier`, `profile_url` |
| what was found | `data_snapshot` JSONB |
| when it appeared / was last seen | `first_found_at`, `last_seen_at` |
| monitoring cadence | `last_checked_at`, `check_count` |
| removal lifecycle incl. reappearance | `status` (… `removed`, `verified_removed`, `relisted`) |
| relative rather than user | `family_member_id` |

`profile_identifier` is the join key that makes month-over-month tracking work.
The scrapers already produce stable ones: Zaba exposes a 64-char content hash
(`data-id`), and FPS/NPD/AnyWho profile URLs contain durable record ids.

### Fields that survive only inside JSONB

These are extracted and correct, but land in `data_snapshot` where nothing can
filter on them:

| field | source | why it might deserve a column |
|---|---|---|
| phone **line type** (Mobile / Landline) | zaba, anywho | a landline is household-shared; a mobile identifies one person. Directly relevant to the dedup false-positive problem below. |
| phone **carrier** | zaba, anywho | |
| phone **first reported** date | zaba | age of an exposure |
| address **county** | zaba | |
| address **lat/long** | zaba, fps | |
| address **residency years** (`2005-2025`) | anywho | recency ranking; which address is current |
| `dateOfBirth` | npd | more precise than a derived age |
| `aliases` at profile level | zaba | |

None of this is urgent. It is worth deciding deliberately rather than
discovering later that a needed filter lives inside a blob.

---

## Stage 4 — enrichment

**Destination:** `quickscan_enrichment`

| produced | column |
|---|---|
| emails found | `emails_found TEXT[]` |
| holehe outcome | `holehe_status`, `services_found TEXT[]`, `holehe_ms` |
| leakcheck outcome | `leakcheck_status`, `breaches JSONB`, `leakcheck_ms` |
| cost | `phase1_cost_usd`, `phase2_cost_usd`, `total_cost_usd` |

### The schema cannot currently express "we could not tell"

`holehe_status` is `pending | success | failed | no_auth | timeout`. But holehe
answers for only **47 of 121** targets — 65 sites block it, 9 modules are
broken. So two very different runs both record `success` with an empty
`services_found`:

- every site answered, none had an account
- 65 sites refused, so we genuinely do not know

The UI renders both as *"no accounts found."* For a product telling people what
is exposed about them, that is the worst possible failure direction.

Both enrichers already report this and the data is being discarded at the
schema boundary:

| enricher reports | needs a home |
|---|---|
| `services_checked`, `services_rate_limited` | holehe coverage |
| `fields_exposed` (password, dob, ip …) | leakcheck — arguably the most user-meaningful field it returns |
| `breach_count` vs `len(sources)` | can differ when sources are withheld |
| per-breach `date` / `year` | fits inside `breaches` JSONB already |
| `rate_limited` as distinct from `failed` | leakcheck quota is ~10 calls/window |

Minimum fix: add `services_checked` / `services_unavailable` integers, and
allow `rate_limited` in both status checks.

---

## Stage 5 — user confirmation

Onboarding writes to `user_emails`, `user_phones`, `user_addresses`,
`user_aliases`. Each already has `source` and `user_confirmed_status` /
`confirmed_at`.

That is the right separation, and worth stating explicitly: **broker-observed
data and user-asserted data are different things.** `exposures` is what brokers
publish; the `user_*` tables are what the user confirms is theirs, and become
the criteria for ongoing monitoring. A broker claim the user rejected must
still be storable as an exposure — otherwise you lose the ability to say "this
site is publishing something wrong about you."

---

## Mismatches to fix before data accumulates

**1. `scrape_results.target` rejects half the sources.**
`CHECK (target IN ('fps','anywho','zabasearch','npd'))`. Inserts for `holehe`
and `leakcheck` fail.

**2. `zaba` vs `zabasearch`.** This repo emits `zaba`
(`BrokerName.ZABA = "zaba"`); the schema says `zabasearch`. Pick one, or every
join needs translation.

**3. No raw response archive.** `scrape_results` stores parsed JSONB only.

This one is worth weight. During the extraction work in this repo, AnyWho was
silently returning 3 of 11 addresses, FPS was fabricating phone numbers out of
profile-URL digits, and three full-profile scrapers were inventing values. All
of it wrote plausible-looking rows. With the raw HTML archived, every
historical scan could be re-parsed once the parser was fixed. Without it, every
scan taken before a fix is permanently degraded and the only remedy is paying
to re-scrape — by which time the broker's page may have changed.

Recommended: archive the raw response to object storage (an AnyWho profile is
~478KB, too large for a column), keyed from `scrape_results`. It also gives
evidence for removal disputes: *here is the page that exposed you, on this
date.*

**4. No parser version stamp.** Add one to `scrape_results` so "which rows need
re-parsing after fixing AnyWho?" is a query rather than an investigation.

---

## Open questions

1. **Third-party PII.** `family_members`, relatives in `exposures.data_snapshot`,
   and associates are real people who never signed up. A privacy company
   accumulating a graph of non-consenting individuals should decide retention
   and access deliberately.
2. **Email prioritisation.** `sequence_runner` enriches only `sorted(emails)[0]`.
   For `oehring` that picks `ja_oehring50@hotmal.com` — a typo'd domain, itself
   broker garbage — over `jaoehring@gmail.com`, which has 8 breaches and 7
   accounts. Interacts with leakcheck's ~10-call quota.
3. **Dedup weighting.** `dedup_engine` scores name 45, location 35, age 10, plus
   an unconditional +10. Phone and relatives contribute nothing, despite being
   the strongest cross-broker signals observed (the same phone and the same
   relative appear in all four brokers). Address and phone should weigh highest
   — but they are also exactly what spouses share, so name has to act as a gate
   rather than another weighted term.
4. **Re-scan semantics.** Does a repeat scan update `exposures` rows in place
   (preserving `first_found_at`) or insert new ones? The monitoring product
   depends on the former.
