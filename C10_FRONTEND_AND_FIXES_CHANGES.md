# C10 Frontend + Two Deploy-Blocking Bug Fixes — Changes

## 1. Bug fix: missing `COPY.*` keys (frontend build blocker)

`frontend/lib/copy.ts` was missing ~15 keys that `sell/page.tsx`,
`stock/page.tsx`, and `components/scanner/BarcodeScanner.tsx` already
referenced (`SELL_SCAN_NOT_FOUND`, `SELL_CREDIT_CUSTOMER_REQUIRED`,
`SELL_MIXED_AMOUNTS_MISMATCH`, the split-payment labels, credit-customer
capture labels, `SCANNER_*`, and `STOCK_NEW_CATEGORY_*`). This is a
`tsc`/Next.js compile error, not a runtime bug — it would fail the
build. Added all missing keys in English; added Swahili translations
for the `SELL_*`/`SCANNER_*` set (the `STOCK_NEW_CATEGORY_*` /
`STOCK_NEW_PRODUCT_*` group has no Swahili translation yet at all —
pre-existing gap, not introduced here, flagged but not fixed).

Verified via `npx tsc --noEmit` — zero errors after the fix (baseline
before the fix showed ~15 `Property does not exist on type` errors at
these exact call sites).

## 2. Bug fix: `@zxing/browser` missing from `package.json`

Root cause of four consecutive failed Vercel deploys. Installed via
`npm install @zxing/browser --save`, which updated both
`package.json` and `package-lock.json`.

## 3. Bug fix: fixed-ratio auto-fill was dead code

`catalog/serializers.py`'s `ProductUnitWriteSerializer.validate()`
raised `PRODUCT_UNIT_NEEDS_RATIO` for any non-root unit with no
`ratio_to_parent` supplied — before the view's own auto-fill logic
(for litre:ml, kg:g, dozen:piece) ever got a chance to run. Since DRF
calls `serializer.is_valid(raise_exception=True)` first, the view's
pre-fill code was unreachable. Fixed by teaching `validate()` to check
`get_fixed_ratio()` itself before rejecting a missing ratio — a
missing ratio is now only an error when the (parent, child) pair has
no fixed conversion.

**Not run against Django's test suite here** (no Python/Postgres
env in this environment) — verified by tracing the exact DRF
validation path by hand. Recommend running the project's existing
catalog/inventory test scripts (the 18/18 and 25/25 DRF `APIClient`
checks mentioned in the pre-pilot doc) against this before deploying.

## 4. C10 frontend — pack-to-unit selling / repackaging UI

New:
- `frontend/lib/types.ts` — `ProductUnit`, `RepackageEvent` types;
  `CartItem.productUnit?` field
- `frontend/lib/catalog.ts` — `listProductUnits`, `createProductUnit`,
  `updateProductUnit`, `deleteProductUnit`
- `frontend/lib/inventory.ts` — `listRepackageEvents`,
  `createRepackageEvent`
- `frontend/lib/copy.ts` — full English + Swahili copy for the unit
  manager, repackage screen, and sell-mode form picker
- `frontend/components/product/ProductUnitManager.tsx` — a product's
  sellable-form tree: add/edit/delete a child unit, choose shared-pool
  vs repackaged, set ratio/price/sellability. Wired into the Stock
  page's product detail drawer.
- `frontend/app/(app)/repackage/page.tsx` — new screen: pick a
  product, pick a from/to unit pair among its repackaged children,
  enter quantities (with a live expected-yield/loss preview), submit,
  see recent history for that product. Owner/manager only, matching
  the API's permission tier.
- `frontend/components/product/UnitPickerModal.tsx` — sell-mode modal
  listing a product's sellable forms with live availability/price;
  used from a small "⋯" affordance added to `ProductCard`.

Modified (`frontend/app/(app)/sell/page.tsx`):
- `ProductCard` gained an `onChooseForm` prop and the "⋯" button
- `addToCart` now only matches a product's *default* (non-unit) cart
  line, so a plain sale and a unit-based sale of the same product can
  coexist as separate cart lines
- New `addUnitToCart(product, unit)` — adds/increments a unit-specific
  line, capped at that unit's `available_quantity`
- `removeFromCart` / `incrementQty` / `decrementQty` now take an
  optional `unitId` and match on `(productId, unitId)` instead of just
  `productId`
- `CartRow` shows the unit's own price/label when `item.productUnit`
  is set; cart `total` uses `item.productUnit?.selling_price` when
  present
- Sale payload now sends `{ product_unit_id, quantity }` instead of
  `{ product_id, quantity }` for unit-based lines — matches the
  existing `TransactionItemCreateSerializer`'s three mutually-exclusive
  line-item shapes exactly

**Verified:** `npx tsc --noEmit` clean across the whole frontend after
all of the above (zero errors). A full `npm run build` could not be
completed in this sandbox — it fails at the Google Fonts fetch step
(`fonts.googleapis.com` isn't reachable from this network), which is
an environment restriction here, not a code issue; Vercel's build
environment has open internet access and won't hit this.

**Not built yet:** a migration path for existing products to opt into
multi-unit tracking, and cost-price allocation down a repackaging
chain — both were already flagged as open in the pre-pilot doc and are
unchanged by this pass.
