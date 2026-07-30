# BizYangu — Phase 7 built, Phase 9 audited against Build Plan v3

Extract over your project root — paths match the real repo exactly.

## Part 1 — Phase 7: Reports: growth & profit graphs (built)

Build Plan v3's Phase 7 checklist, and what was actually done:

- [x] **Revenue-over-time line chart** — new `GET /api/v1/reports/growth/`
  endpoint returns the same `daily_breakdown` shape as `/reports/period/`
  (day, revenue, transaction_count). Rendered as a `recharts` `LineChart`
  in a new **Growth** tab on the Reports page (period's existing bar chart
  is untouched — this is an addition, not a replacement).
- [x] **Profit/margin trend** — this needed a new endpoint, not a reshape
  of `/reports/products/`. `/reports/products/` only aggregates margin
  over the *whole* selected window in one number per product; a trend
  needs margin *per day*. New helper `_daily_margin_trend()` groups
  `TransactionItem` rows (not `Transaction` totals) by day, using each
  item's snapshotted `cost_price` — same "don't guess a missing cost"
  rule already used in `product_performance_report` (items with no
  `cost_price` are excluded from the cost/margin sums, never zero-filled).
- [x] **Period-over-period growth indicator** — `_previous_period()` takes
  whatever `start`/`end` window was requested and computes the
  immediately preceding window of the same length, so "this week vs last
  week" and "this month vs last month" both fall out of the same
  function. `revenue_growth_pct` and `transaction_growth_pct` are `null`
  (not `0` or an error) when there's nothing to compare against yet —
  frontend shows "not enough history" instead of a misleading badge, same
  pattern as the existing dashboard's yesterday-comparison.
- [x] **Visual treatment for service-vs-goods businesses** — there's no
  `has_inventory` flag on `Business` yet (that's explicitly a **Phase 9**
  item per the plan, not built yet — see Part 2). So this shipped as an
  inferred `business_mode: 'goods' | 'service'` on the response: `'goods'`
  if the business has any stock-tracked product *or* any margin data in
  the window, else `'service'`. The frontend's margin/profit chart only
  renders at all when `business_mode === 'goods'` — a service business's
  Growth tab shows only the revenue trend and the growth badge, no
  stock/margin language. **Flagged, not silently done:** once Phase 9
  lands a real `has_inventory` flag, this inference should be replaced
  with the real flag rather than left as a heuristic.

### Files changed (Phase 7)

| Path | What changed |
|---|---|
| `backend/apps/reports/views.py` | New `growth_report` view + `_daily_margin_trend`, `_previous_period`, `_pct_change` helpers |
| `backend/apps/reports/urls.py` | New route: `GET /api/v1/reports/growth/` |
| `frontend/lib/reports.ts` | New types (`GrowthReport`, `MarginTrendPoint`, `PeriodTotals`, `BusinessMode`) + `getGrowthReport()` |
| `frontend/lib/copy.ts` | New `REPORTS_GROWTH_*` / `REPORTS_TAB_GROWTH` keys, English + Kiswahili |
| `frontend/app/(app)/reports/page.tsx` | New **Growth** tab: period-over-period badge, revenue line chart, conditional margin line chart |

No migrations needed — this phase reads existing `Transaction`/
`TransactionItem`/`Product` data only, no new models or fields.

### Nothing to run
No `migrate` needed for this patch. Just drop the files in and the new
`/reports/growth/` route + Growth tab are live.

---

## Part 2 — Phase 9 audit: NOT implemented (frontend has non-functional groundwork only)

You asked me to check whether Phase 9 ("Sell-without-inventory +
progressive catalog growth") is partially or fully built. Short answer:
**the backend has none of it, and the frontend pieces that exist would
fail against the current backend if used today.** Here's the checklist
from the plan, item by item.

### 9.1 "Selling never stops for a missing product"

**Plan asks for:** `TransactionItem.product` nullable, freeform `name` +
`unit_price` fields for the unreconciled case.

**What's actually in the repo:**
- `backend/apps/transactions/models.py` — `TransactionItem.product` is
  still `ForeignKey(..., on_delete=models.PROTECT)` with **no `null=True`**.
  No `name` or `is_reconciled` field exists on the model at all.
- `backend/apps/transactions/serializers.py` — `TransactionItemCreateSerializer.product_id`
  is a **required** `UUIDField()`. There is no code path that accepts a
  freeform name/price instead.
- **But** `frontend/lib/types.ts` already declares `TransactionItem.name`,
  `is_reconciled`, and a nullable `product` — fields the backend doesn't
  have. And `frontend/app/(app)/sell/page.tsx` already has a working
  `addCustomToCart()` that builds a synthetic client-only product and, on
  checkout, sends `{ name, unit_price, quantity }` instead of
  `{ product_id, quantity }` for items marked `isCustom`.

**Net effect: this is drafted-ahead-of-backend, not "partially built."**
If a cashier hits "Sell" on a custom item today, the request the frontend
sends doesn't match what `TransactionItemCreateSerializer` accepts —
`product_id` is required and there's no `name`/`unit_price` alternative
path, so the sale would fail validation. Nothing in this slice is usable
end-to-end yet.

### 9.2 Reconciliation queue in Stock

**Plan asks for:** owner assigns each unreconciled item to an existing
product or creates a new one, from the Phase 8 taxonomy.

**What's actually in the repo:** nothing. No "unreconciled items" section
in `frontend/app/(app)/stock/page.tsx` — the only stock-page modal is the
existing "Add product" one, unrelated to reconciliation. No backend
endpoint for listing or resolving unreconciled items. (The only
"reconcil-" hits in the codebase are the *M-Pesa payment* reconciliation
feature — a completely different, already-shipped feature — not product
reconciliation.)

### 9.3 Onboarding against the Phase 8 taxonomy

**Plan asks for:** select business type → see Phase 8's categories for
that type → optionally add starter items, or skip.

**What's actually in the repo:**
- `frontend/app/setup/page.tsx` picks a business type from a small
  hardcoded list (`DUKA`, `HARDWARE`, `BOUTIQUE`, `STATIONERY`, `CUSTOM`)
  matching `Business.Type` — this predates Phase 8 and doesn't reference
  the taxonomy at all.
- `frontend/app/onboarding/products/page.tsx` is a blank manual/CSV
  entry form (add up to 5 products by typing name + price + stock) — no
  category picker, no taxonomy-driven suggestions. This is actually a
  step *before* even v2's old Phase 9 ("curated preset lists"), let alone
  v3's taxonomy-driven version.
- Nothing in `backend/bizyangu/settings*.py` or any `urls.py` serves the
  `knowledge/` JSON to the frontend at all — confirmed by grep, zero
  references anywhere in `backend/` or `frontend/` to
  `business_types.json`, `categories.json`, or the `templates/` files.
  This matches what `knowledge/README.md` itself says: *"none of this
  JSON is loaded by backend/ yet... this is expected but it means wiring
  knowledge/ into onboarding/reconciliation... is still open work for
  Phase 9, not something already half-built."* The audit confirms that
  note is still accurate — nothing has changed since it was written.

### 9.4 `has_inventory` flag

Not present on `Product`, `Business`, or anywhere else in the schema.
`Product.track_stock` exists but is a different, pre-existing concept
(whether a specific stocked product's quantity is tracked) — it isn't
the goods-vs-service business-level flag the plan describes.

### 9.5 Within-business suggestions (§2.3, fast track)

Not present. No code path surfaces "other common brands in this category"
after 2+ items are added — there's no link between `catalog.Product`/
`catalog.Category` and any `knowledge/` taxonomy id to make that
suggestion from.

### 9.6 Reports handle unreconciled items gracefully

Moot until 9.1–9.2 exist — there's no such thing as an unreconciled item
in the backend today, so there's nothing for reports to handle specially.
(Current reports already correctly exclude items with `product_id` null
from top-products/margin breakdowns via `.exclude(items__product_id__isnull=True)`,
which incidentally means the day this feature *does* ship, that part of
the reports code won't need to change.)

## Sign-off

| Checklist item | Status |
|---|---|
| `TransactionItem.product` nullable + freeform fields | ❌ Not built (model/serializer still require a real product) |
| Sale flow accepts freeform name+price | ⚠️ Frontend UI + payload shape exist (`sell/page.tsx`); **non-functional** — backend rejects it |
| Reconciliation queue in Stock | ❌ Not built (no UI, no endpoint) |
| Taxonomy-driven onboarding | ❌ Not built (onboarding predates Phase 8, no taxonomy reference anywhere) |
| `has_inventory` flag | ❌ Not built |
| Within-business suggestions | ❌ Not built |
| Reports handle unreconciled items | ➖ Moot — nothing to handle yet, but already-safe for when it lands |

**Overall: Phase 9 is not implemented.** The one place it looks
"partially" done — `frontend/lib/types.ts` and `sell/page.tsx`'s custom-
item cart flow — is UI built ahead of the backend, using a payload shape
the backend doesn't accept. I'd flag that explicitly rather than count it
as partial progress, since shipping it as-is would just produce a
confusing 400 the first time a cashier tries it. Phase 8 (the taxonomy
JSON itself) is genuinely done and validated per its own README — Phase 9
is the still-open work of wiring that taxonomy and the sell-without-
inventory flow into the app.
