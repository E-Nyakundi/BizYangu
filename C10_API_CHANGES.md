# C10 (pack-to-unit selling) — serializers + API views

Extract over your project root — paths match the real repo exactly. Backend
models for this were already in place (ProductUnit, RepackageEvent,
StockMovement.product_unit) from the prior session; this delta adds the
API layer on top of them. No new migrations — model shape was unchanged.

## New endpoints

**catalog app** — `apps/business.Business`-scoped, same auth/tenant pattern
as everything else:

- `GET  /api/v1/catalog/products/{id}/units/` — a product's sellable-form
  tree, each with a computed `available_quantity`. Open to any
  authenticated staff (Sell mode will need this).
- `POST /api/v1/catalog/products/{id}/units/` — add a form. Owner/manager
  only. Validates root/parent/ratio rules server-side (mirrors
  `ProductUnit.clean()`) and auto-fills true unit-of-measure ratios
  (litre↔ml, kg↔g, dozen↔piece) when the pair is a fixed conversion and
  none was supplied.
- `GET/PATCH/DELETE /api/v1/catalog/products/{id}/units/{unit_id}/` —
  single form. Delete is blocked for the root unit and for any unit that
  still has children.

**inventory app**:

- `GET  /api/v1/inventory/repackage/` — repackaging history, optional
  `?product=id` filter.
- `POST /api/v1/inventory/repackage/` — record a repackaging event
  (owner/manager only, `burst_write` throttle, same tier as sale/stock-in).
  Validates the from/to unit pairing, checks `from_unit.available_quantity()`
  covers the requested amount, computes `expected_yield`/`loss_quantity`
  from the ratio in effect right now, and writes two `StockMovement` rows
  (`REPACKAGE_OUT` on the source pool, `REPACKAGE_IN` on the destination) —
  built inside the same atomic-block-then-respond pattern as
  `settle_payment`/`create_refund`/`void_transaction`, so a serializer or
  messages-key error rolls the whole thing back instead of committing
  silently behind a 500.

~25 new `MESSAGES` keys added (English + Swahili) for the above.

## Also fixed in this pass

The stale duplicate migration
`transactions/0004_transactionitem_is_reconciled_transactionitem_name_and_more.py`
had reappeared in this zip (the same bug fixed once before during the
Phase 5 pass — see the settle_payment incident). Deleted again;
`makemigrations --check --dry-run` is clean.

## Verified

Ran a full functional pass against an in-memory SQLite DB through DRF's
`APIClient` (not just unit tests of the model methods) covering: root/child
unit creation, ratio validation and auto-fill, `available_quantity()`
deriving correctly through a shared-pool child, delete guards (root,
has-children), cashier-vs-owner permission enforcement on both endpoints,
a full repackage (bag → gorogoro) with correct loss calculation and stock
movements, insufficient-stock rejection, cross-product-pairing rejection,
and the history list. All 18 checks passed. `manage.py check` and
`makemigrations --check` both clean.

## Not built yet — flagging for the next step

Selling *from* a `ProductUnit` (Sell mode ringing up "1 stick" instead of
"1 pack") still needs:
- a `TransactionItem.product_unit` field (+ migration)
- `TransactionItemCreateSerializer` accepting `product_unit_id` alongside
  `product_id`
- `create_sale` in `apps/transactions/views.py` deducting via
  `ProductUnit.deduct_sale()` and setting `product_unit` on the
  `StockMovement` it creates, instead of assuming every sale is
  product-level

Deliberately left out of this pass since it touches the live sale path —
worth its own dedicated step before frontend Sell-mode UI work starts.

## Frontend

Not built yet — UI for defining a product's unit tree (product edit
screen), the repackage action (a new screen/modal, likely reachable from
Stock), and Sell-mode support for picking a specific sellable form are
all still open.
