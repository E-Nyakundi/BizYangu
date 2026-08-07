# E18 — Remove crosshair decorative elements

Implements build-plan item E18: "Remove crosshair decorative
elements." Pure deletion, no behavior change.

## What changed

- **`frontend/app/(app)/layout.tsx`** — removed the four
  `<div className="crosshair ch-*">` corner marks and their comment
  block, right at the top of the layout's JSX.
- **`frontend/styles/globals.css`** — removed the `.crosshair` rule set
  (`.crosshair`, `::before`, `::after`) and all four corner-position
  classes (`.ch-tl`, `.ch-tr`, `.ch-bl`, `.ch-br`).
- **Found and fixed in passing:** `.ch-bl`/`.ch-br` were defined
  *twice* in `globals.css` — a pre-existing duplication, unrelated to
  this task, that my first removal pass missed on the first read since
  the two copies weren't adjacent. Both copies are gone now.
- The `body::before` grid-overlay rule (faint background grid, a
  separate visual element under the same old section header) is
  untouched — only its section comment was renamed from "GRID OVERLAY
  & CROSSHAIR MARKS" to "GRID OVERLAY" since crosshairs no longer live
  there.

## Note on this patch

`layout.tsx` in this zip already includes the E19 nested-nav change
from the previous patch (`BizYangu_E19_NavFold.zip`) — this is the
current full state of the file, not a diff on top of your original
upload. If you've already applied E19, just overwrite with this
version; if you haven't, this single file covers both.

## Verified

`npx tsc --noEmit` against the full project — zero errors.

## Files in this patch

| Path | What changed |
|---|---|
| `frontend/app/(app)/layout.tsx` | Crosshair divs removed (includes prior E19 nested-nav change) |
| `frontend/styles/globals.css` | `.crosshair` rules + all `.ch-*` classes removed, including the duplicate copy |
