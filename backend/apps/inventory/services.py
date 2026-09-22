"""
BizYangu — inventory services.

record_stock_count() holds the actual stock-count logic, extracted out
of views.submit_stock_count() so it can be called from two places with
identical behaviour: the live HTTP endpoint, and the offline-sync push
endpoint (apps.sync.views), which has no real DRF request to hand a
view — a device that adjusted stock while offline (a physical count
taken with no signal) needs the exact same validation, stock write, and
notification side effects a live adjustment gets.

Raises StockCountError for every validation-style failure that used to
return a Response directly from the view — same pattern as
apps.transactions.services.SaleError.
"""

import logging

from apps.catalog.models import Product
from apps.core.messages import MESSAGES
from django.db.utils import IntegrityError
from .models import StockMovement

logger = logging.getLogger(__name__)


class StockCountError(Exception):
    """Raised for any validation-style failure in record_stock_count() —
    the same conditions that used to short-circuit submit_stock_count()
    with an error Response. Carries the same user-facing message and,
    where the original returned a specific status code, that code too,
    so both call sites can reproduce the exact same behaviour."""
    def __init__(self, detail, status_code):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def record_stock_count(business, user, product_id, counted_qty, notes='', sync_idempotency_key=None):
    """
    Sets a product's current_stock to counted_qty and records a COUNT
    StockMovement for the audit trail, exactly as views.submit_stock_count
    always has.

    Callers are responsible for running StockCountSerializer themselves
    first (same division of labour as record_sale — this function
    assumes well-typed values) and for the IsOwnerOrManager permission
    check: this is a role-gated action live, and going offline must not
    become a way to bypass that gate, so the sync push handler enforces
    the same role check the live endpoint's permission_classes did
    before ever calling this.

    `sync_idempotency_key`, when given (only the sync push path passes
    one), makes this call safe to retry: if a StockMovement already
    exists with this key, it's returned as-is with no second write —
    mirrors record_sale()'s identical parameter and rationale exactly.

    Raises StockCountError (404) if the product doesn't exist, is
    inactive, or belongs to a different business. Returns the created
    (or, on a retried key, the already-existing) StockMovement —
    callers serialize it themselves.
    """
    if sync_idempotency_key:
        existing = StockMovement.objects.filter(
            business=business, sync_idempotency_key=sync_idempotency_key,
        ).first()
        if existing is not None:
            return existing

    try:
        product = Product.objects.get(id=product_id, business=business, is_active=True)
    except Product.DoesNotExist:
        raise StockCountError(MESSAGES['PRODUCT_NOT_FOUND'], 404)

    qty_before = product.current_stock
    status_before = product.stock_status
    product.current_stock = counted_qty
    product.save(update_fields=['current_stock'])

    try:
        movement = StockMovement.objects.create(
            business=business,
            product=product,
            movement_type=StockMovement.MovementType.COUNT,
            quantity_change=counted_qty - qty_before,
            quantity_before=qty_before,
            quantity_after=counted_qty,
            notes=notes or MESSAGES['STOCK_COUNT_NOTE'].format(quantity=counted_qty),
            created_by=user,
            sync_idempotency_key=sync_idempotency_key,
        )
    except IntegrityError:
        # Same race as record_sale()'s identical guard: a concurrent
        # retry of the exact same queued operation won between our
        # lookup above and this create() — fetch and return that one
        # rather than surfacing a spurious failure. Note current_stock
        # was already written above by this request; if this branch
        # fires, the concurrent winner wrote the same counted_qty (same
        # queued operation, replayed), so no inconsistency results from
        # this request's write "sticking" even though its own
        # StockMovement row didn't get created.
        if sync_idempotency_key:
            existing = StockMovement.objects.filter(
                business=business, sync_idempotency_key=sync_idempotency_key,
            ).first()
            if existing is not None:
                return existing
        raise

    status_after = product.stock_status
    if status_after in ('LOW', 'OUT') and status_after != status_before:
        try:
            from apps.notifications.services import notify_low_stock
            notify_low_stock(product, status_after)
        except Exception:
            logger.exception('Low-stock notification failed for product %s', product.id)

    return movement
