# C8 — Full product-detail editing (dedicated screen)

Implements build-plan item C8: "Full product-detail editing after
onboarding as a dedicated screen." Drop these files into the matching
paths in your repo — same structure as the zip you gave me.

## New

- `frontend/app/(app)/stock/edit/page.tsx` — the dedicated edit screen.
  Reached from Stock → tap a product → "Edit details" in the drawer.
  Static-export-safe: takes the product id as `?id=` (no `[id]` dynamic
  route), same pattern as `app/join/page.tsx`'s invite token.

  Fields: photo (upload/replace/remove), name, barcode, category
  (existing / taxonomy tree with subcategory drill-down / free-typed
  new — same picker as the "Add Product" modal), selling price, cost
  price, unit, low-stock threshold, expiry date, track-stock toggle.
  Also: deactivate/reactivate, and a link through to Repackage for the
  sellable-forms tree (already covered by C10 in the drawer, so not
  duplicated here).

  `current_stock` is deliberately not on this screen — same reasoning
  your own `catalog.ts` comment already had: stock only ever moves
  through a movement-writing endpoint (Add Stock / Loss / Count) so the
  audit trail stays accurate. This screen doesn't touch it.

## Changed

- `frontend/app/(app)/stock/page.tsx` — added an "Edit details" link
  (owner/manager only) in the `ProductDrawer` header, next to the ×.

- `frontend/lib/catalog.ts` — fixed a real bug in `updateProduct`'s
  multipart branch: when an image is attached, `null` payload values
  (e.g. clearing category or expiry_date) were being silently dropped
  from the `FormData` instead of sent, because there's no native
  `null` in multipart. Now sends `''` for those, which DRF's
  related/date fields already treat as "clear this field" for
  form-encoded data — so clearing something on the same edit that also
  swaps the photo now actually clears it.

- `frontend/lib/copy.ts` — added `EDIT_PRODUCT_*` keys (screen title,
  every field label, save/error copy, deactivate flow) plus
  `STOCK_DRAWER_EDIT_DETAILS`, in both `COPY` and `COPY_SW`. The
  Swahili is a draft, consistent with your item 21 note — flag any
  phrasing during your accuracy pass.

- `frontend/app/(app)/sell/page.tsx` — **unrelated pre-existing bug,
  found while typechecking**: `addCustomToCart`'s synthetic `Product`
  literal (used for "sell without inventory" custom items) was missing
  `taxonomy_category_id` / `taxonomy_subcategory_id` / `taxonomy_brand`
  / `expiry_date` — all four are required on the `Product` type but
  weren't being set here, which fails `tsc --noEmit` outright. Added
  empty-string/null defaults. This was breaking a clean typecheck of
  the whole frontend regardless of anything else in this batch.

- `backend/apps/catalog/serializers.py` — `expiry_date` exists on the
  `Product` model (migration 0003) but was never added to
  `ProductSerializer.Meta.fields`, so it was silently unreadable *and*
  unwritable through the API the whole time — same class of gap as the
  taxonomy fields had before your Phase 8 fix. Added it.

- `backend/apps/catalog/views.py` — `product_detail`'s PATCH handler
  had two real gaps relative to the POST/create endpoint:
  1. No validation that an explicitly-given `category` id actually
     belongs to the requesting business — `product_list_create`'s POST
     path checks this, PATCH never did. A bad/foreign id would have
     silently linked a product cross-tenant instead of 400ing.
  2. `category_name` (the get-or-create-by-name path the taxonomy
     picker and "+ New category" use) was never resolved on PATCH —
     `ProductSerializer.category_name` is read-only there by design
     (it's a display field), so anything the edit screen's category
     picker sent for a new/taxonomy category was just silently
     ignored. Fixed by resolving it the same way `product_list_create`
     does, only when no explicit `category` id was already sent.

## Verified

- `npx tsc --noEmit` on the full frontend: clean (after the Sell page
  fix above — it was failing before any of my other changes too).
- `npx next build` gets through compilation/typechecking and only then
  fails trying to fetch Google Fonts — that's this sandbox's network
  allowlist blocking `fonts.googleapis.com`, not a code issue. Worth a
  real build on your end to confirm, but nothing in the failure trace
  touches any file in this batch.
- Did not run the Django test suite / migrations check — no DB
  available in this sandbox. The two view/serializer changes don't
  touch models or need a migration (both fields already exist), but
  flag it if anything looks off against your actual data.

## Not done in this batch

- Swahili accuracy pass on the new copy (yours per item 21 — flagged
  above).
- No new backend tests written for the two PATCH fixes (category
  cross-tenant validation, category_name resolution). Worth a couple
  of quick ones given they're real security/correctness fixes, not
  just the new screen.
