# E19 — Nav bar overload (Payments/Creditors nested under Reports)

Implements build-plan item E19: "Nav bar overload on mobile — fold
Payments/Creditors into Reports." This supersedes the first pass
(`BizYangu_E19_NavFold.zip`) — that version moved Payments/Creditors
to a same-level link row on the Reports page, which wasn't the actual
ask. This version does real parent/child nesting.

## Design

- **Desktop (≥768px):** the side nav shows Reports with Payments and
  Creditors nested directly underneath it — always visible, never
  collapsed behind a click. Visual style is a Reddit-thread-style
  connector: a vertical line down the left edge with the children
  indented off it (`.nav-nested` in `globals.css`).
- **Mobile (<768px):** the bottom nav can't show a nested tree (icons
  in a row, no vertical space), so it stays flat — Home, Sell, Stock,
  Reports, Settings. The mobile equivalent of "nested" lives on the
  Reports page itself: a collapsed-by-default accordion ("▸ Manage")
  that expands to the same two links, tap to open. Same visual nesting
  style (`.nav-nested`) once expanded, just collapsed until tapped.
- Both are owner/manager-only, same gate the old standalone nav items
  carried — now applied per-child in `NAV_ITEMS` rather than at the
  top level.
- `/payments` and `/creditors` themselves are still untouched, full
  pages — nesting is a navigation-affordance change, not a page merge.

## Files in this patch

| Path | What changed |
|---|---|
| `frontend/app/(app)/layout.tsx` | `NAV_ITEMS`'s `/reports` entry gained a `children` array (Payments, Creditors). Desktop side-nav rendering now renders each item's visible (role-filtered) children in a `.nav-nested` block right under it. Mobile bottom nav is untouched — it only reads `icon`/`label`/`href` per top-level item, so children never render there automatically. |
| `frontend/app/(app)/reports/page.tsx` | Replaced the old flat "Manage" link row with a `.mobile-only` collapsed-by-default accordion (`manageExpanded` state) rendering the same two links inside a `.nav-nested` block once opened. |
| `frontend/styles/globals.css` | New utilities: `.desktop-only` / `.mobile-only` (767px breakpoint, matching the existing nav breakpoint) and `.nav-nested` (the Reddit-thread connector line + indent, shared by both the sidebar and the mobile accordion so they look identical). |
| `frontend/lib/copy.ts` | Unchanged from the first pass — `REPORTS_MANAGE_TITLE`/`_PAYMENTS`/`_CREDITORS` keys are reused for the accordion label and links. |

## Verified

`npx tsc --noEmit` against the full project — zero errors. (Full
`next build` also fetches Google Fonts at build time; unrelated to
this change and untestable in this sandbox, but will run normally on
Vercel.)

## Suggested manual check

- Desktop, OWNER/MANAGER: confirm Payments and Creditors show nested
  under Reports in the sidebar at all times, connector line visible,
  clicking either navigates correctly, active-state highlighting still
  works on the nested links.
- Desktop, CASHIER: confirm no nested children appear under Reports.
- Mobile (<768px), OWNER/MANAGER: confirm bottom nav is flat (5
  icons), and on the Reports page the "▸ Manage" row is collapsed by
  default and expands on tap.
- Mobile, CASHIER: confirm the "▸ Manage" row doesn't render at all.
