# E19 — Nav bar overload (Payments/Creditors folded into Reports)

Implements build-plan item E19: "Nav bar overload on mobile — fold
Payments/Creditors into Reports." Drop these files into the matching
paths in your repo.

## What changed

- **Nav bar** (`frontend/app/(app)/layout.tsx`) — `NAV_ITEMS` cut from
  7 to 5: Home, Sell, Stock, Reports, Settings. "Payments" and
  "Creditors" removed as top-level nav entries.
- **Routes unchanged.** `/payments` and `/creditors` are still full,
  untouched pages — nothing about M-Pesa reconciliation or credit
  settlement moved or was rebuilt. They're not folded in as report
  tabs (they're operational screens with their own actions — settling
  a payment, reconciling M-Pesa — not read-only reports), so folding
  them into Reports means giving them an entry point there, not
  merging their UI into a tab pane.
- **Reports page** (`frontend/app/(app)/reports/page.tsx`) — new
  "Manage" row above the report tabs, owner/manager only (same gate
  the old nav items carried via `roles: ['OWNER', 'MANAGER']`), with
  two links out to `/payments` and `/creditors`. Reads
  `useAuthStore().user.role` directly since Reports previously had no
  role-gating of its own.
- **Copy** (`frontend/lib/copy.ts`) — added `REPORTS_MANAGE_TITLE`,
  `REPORTS_MANAGE_PAYMENTS`, `REPORTS_MANAGE_CREDITORS` in both EN and
  SW.
- **Bonus fix, found while editing this file:** `COPY_SW` was missing
  `NAV_CREDITORS` entirely — English had it, Swahili didn't. Unrelated
  to E19 but a one-line fix sitting right next to what I was already
  touching, so included here rather than opened as a separate item.

## Why this shape

A cashier (no `roles` restriction) never saw Payments/Creditors in the
nav anyway — this only visibly changes things for OWNER/MANAGER, who
now find them one tap into Reports instead of a standing nav slot.
Both pages already sit inside the `(app)` layout, so the remaining
5-item nav (still visible on `/payments` and `/creditors` themselves)
means nobody is ever stranded without a way back.

## Files in this patch

| Path | What changed |
|---|---|
| `frontend/app/(app)/layout.tsx` | `NAV_ITEMS` trimmed to 5, comment explaining the fold |
| `frontend/app/(app)/reports/page.tsx` | New owner/manager-only "Manage" link row above the tabs |
| `frontend/lib/copy.ts` | 3 new EN/SW key pairs + missing `NAV_CREDITORS` (SW) backfilled |

## Not touched

- `frontend/app/(app)/payments/page.tsx` and
  `frontend/app/(app)/creditors/page.tsx` — zero changes, still the
  same full pages.
- Desktop side-nav layout code path — same component, same fix applies
  to both automatically since they share `NAV_ITEMS`.

## Suggested manual check before calling this done

- Log in as CASHIER: confirm nav still shows 5 items, no Manage row
  visible if you navigate to Reports directly (it shouldn't show for
  a role that never had Payments/Creditors access anyway).
- Log in as OWNER or MANAGER: confirm the Manage row appears on
  Reports, both links land on the right page, and the 5-item nav still
  gets you back out.
- Mobile width (<768px): confirm the bottom nav now comfortably fits 5
  icons without the cramped wrapping the 7-item version had.
