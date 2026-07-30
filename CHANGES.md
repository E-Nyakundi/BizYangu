# BizYangu — Session Patch: STK Push fix, Refund → amount-only, Unit choices fix

Extract over your project root — paths match the real repo exactly.

## Bug 1 — STK push always says "already been processed"

**Root cause:** `create_sale` hardcoded every new sale's `payment_status` to
`CONFIRMED`, regardless of payment method. For M-Pesa sales this is wrong — the whole
payments module (`services.py`, the callback, the polling endpoint) was correctly
built assuming M-Pesa sales start `PENDING` and get flipped to `CONFIRMED` only once
the customer actually pays. Since they were already `CONFIRMED` the instant you hit
"Sell," `initiate_stk_push`'s check (`if payment_status != PENDING: reject`) failed on
literally every attempt.

**Fix:** `create_sale` now sets `PENDING` for `payment_method=MPESA`, `CONFIRMED` for
everything else (cash/credit/mixed have no separate confirmation step).

## Bug 2 — Refund always failed with a generic error, redesigned to amount-only

Two real bugs: `RefundItemSerializer.transaction_item_id` was typed as `UUIDField()`
when `TransactionItem.id` is a plain integer — every refund with real item IDs failed
validation outright. And separately, the itemized-quantity design was the wrong shape
for how you actually think about refunds.

**Fix — rebuilt around your instruction directly:** the user types one number — the
KES amount being refunded — and nothing else. No items, no quantities, no
percentages.
- `POST /api/v1/transactions/refund/` now takes `{ transaction_id, amount, reason }`.
- Internally, that amount gets apportioned across the sale's line items
  proportionally (purely to keep per-product stock counts accurate) — that math never
  reaches the API response or the UI.
- The refund modal is one amount field (pre-filled with the full remaining refundable
  amount, so a full refund is one tap), a reason field, confirm. Shows "Refundable up
  to KES X" so there's a visible ceiling without needing to compute anything.
- Partial refunds still work, validated against total KES remaining on the sale.

## Bug 3 — Adding a product with most unit types failed silently

**Root cause:** the Add Product form offers 7 unit buttons — `pcs, kg, g, l, ml, pack,
box` — the only place a unit gets picked anywhere in the app. The backend only
accepted `piece, kg, litre, pack, custom`. Only `kg` and `pack` happened to match on
both sides — every other button (`pcs`, `g`, `l`, `ml`, `box`) failed validation on
every submission. This is why "sugar in kg" worked and "pieces" didn't — and grams,
litres, ml, and box were just as broken, you'd simply not hit them yet.

**Fix:** `Product.Unit` rewritten to match the frontend's real set exactly, with a
data migration translating any already-created rows (`piece`→`pcs`, `litre`→`l`,
`custom`→`pcs`) so nothing existing breaks.

## Files in this patch

| Path | What changed |
|---|---|
| `backend/apps/transactions/views.py` | STK push fix + refund rewritten to amount-only with internal apportionment |
| `backend/apps/transactions/serializers.py` | `RefundCreateSerializer` simplified to `{transaction_id, amount, reason}` |
| `backend/apps/transactions/models.py` | Unchanged from last patch (refund FKs) — included for completeness |
| `backend/apps/transactions/migrations/0002_add_refund_links.py` | Unchanged — still needs `migrate` if not already applied |
| `backend/apps/transactions/urls.py` | Unchanged — included for completeness |
| `backend/apps/payments/views.py` | Unchanged from the M-Pesa reconciliation fix — included for completeness |
| `backend/apps/core/messages.py` | Refund messages simplified to amount-based |
| `backend/apps/catalog/models.py` | Fixed `Product.Unit` choices to match what the frontend actually sends |
| `backend/apps/catalog/serializers.py` | No functional change — included for completeness |
| `backend/apps/catalog/migrations/0002_fix_unit_choices.py` | New migration + data migration for existing rows on old unit values |
| `frontend/lib/transactions.ts` | `refundTransaction()` now takes `{transaction_id, amount, reason}` |
| `frontend/lib/types.ts` | Unchanged from last patch — included for completeness |
| `frontend/lib/copy.ts` | Refund copy simplified to amount-based strings, English + Kiswahili |
| `frontend/app/(app)/sell/transactions/page.tsx` | `RefundModal` rebuilt as a single amount field |

## Run this first
```bash
python manage.py migrate
```
Two migrations need to apply: `transactions/0002_add_refund_links` (if not already
applied from the last patch) and `catalog/0002_fix_unit_choices` (new this message —
also data-migrates any products already saved with the old unit values).

## Still open from earlier in this session
- **M-Pesa PDF statement import** — deferred until you paste the LifeApp parser code.
- **STK timeout cleanup job** — right now, if a customer ignores the STK prompt and
  Daraja's timeout callback never arrives (network issue, e.g. the tunnel dropping),
  the sale sits `PENDING` with stock already deducted, with no automatic cleanup.
  There's a manual fix (owner/manager can void it any time from Transaction History —
  `void_transaction` has no restriction on `payment_status`), but nothing automatic.
  Offered to build a periodic cleanup command reusing the existing
  `_void_transaction_for_failed_payment` logic — not built yet, say the word.
