# Dashboard Readiness

**Status:** Gated — dashboard routes are dev-only until production-ready.
**Last Updated:** March 2026

---

## Current Gate

Dashboard routes are wrapped in a `DevOnly` guard in `apps/app/src/App.tsx`.

```tsx
// apps/app/src/App.tsx
function DevOnly({ children }: { children: ReactNode }) {
    if (!import.meta.env.DEV) return <Navigate to="/scanning-started" replace />;
    return <>{children}</>;
}
```

In **production**, any attempt to hit a dashboard route redirects to `/scanning-started`.
In **development** (localhost), routes pass through normally — no change to dev workflow.

### Gated routes

```
/dashboard
/dashboard/home
/dashboard/dark-web
/dashboard/exposures
/dashboard/tasks
/dashboard/activity
/transactions
```

---

## Post-Onboarding Redirect

When a user completes onboarding they are currently sent to `/scanning-started`.

The `navigate("/scanning-started")` calls live in these files — replace with the correct destination when the dashboard is ready:

```
apps/app/src/pages/onboarding/progress.tsx        (4 locations)
apps/app/src/pages/onboarding/primary-info.tsx    (2 locations)
apps/app/src/pages/onboarding/emails.tsx          (2 locations)
apps/app/src/pages/onboarding/aliases.tsx         (2 locations)
apps/app/src/pages/onboarding/phone-numbers.tsx   (2 locations)
apps/app/src/pages/onboarding/addresses.tsx       (2 locations)
```

Quick grep to find them all at once:
```bash
grep -rn 'navigate("/scanning-started")' apps/app/src/pages/onboarding/
```

---

## To Open Dashboard for Production

1. **Remove the `DevOnly` wrapper** from all dashboard routes in `apps/app/src/App.tsx` (the `DevOnly` component can be deleted entirely).
2. **Update post-onboarding redirects** — change `navigate("/scanning-started")` to the correct destination (likely `/dashboard/home` or a new transition page) across the onboarding files listed above.
3. **Review each dashboard page** against the checklist below before flipping the gate.

---

## Dashboard Page Checklist

| Page | Route | File | Ready? |
|:-----|:------|:-----|:------:|
| Home | `/dashboard/home` | `views/Dashboard/DashboardHome.tsx` | ☐ |
| Dark Web | `/dashboard/dark-web` | `pages/dashboard/dark-web.tsx` | ☐ |
| Exposures | `/dashboard/exposures` | `pages/dashboard/exposures.tsx` | ☐ |
| Tasks | `/dashboard/tasks` | `pages/dashboard/todo.tsx` | ☐ |
| Activity | `/dashboard/activity` | `pages/dashboard/activity.tsx` | ☐ |

---

## Related Docs

- `docs/DESIGN_SYSTEM.md` — UI tokens and component patterns
- `docs/CICD.md` — deployment and branch strategy
