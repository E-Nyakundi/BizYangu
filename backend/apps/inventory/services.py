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
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.utils import IntegrityError

from apps.catalog.models import Product, ProductUnit
from apps.core.messages import MESSAGES
from .models import RepackageEvent, StockMovement

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


class RepackageError(Exception):
    """Raised for every validation-style failure in record_repackage() —
    the same conditions that used to return a Response directly from
    views.repackage_list_create. Carries the same user-facing message
    and status code, so both call sites (live view, offline sync push)
    reproduce the exact same behaviour. Same pattern as StockCountError
    and apps.transactions.services.SaleError."""
    def __init__(self, detail, status_code):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def record_repackage(
    business, user, from_unit_id, to_unit_id, quantity_consumed, quantity_produced,
    notes='', sync_idempotency_key=None,
):
    """
    Converts one physical form of a product into another, exactly as
    views.repackage_list_create always has: validates the from/to unit
    pairing, checks available stock on from_unit, deducts it, credits
    to_unit, and records both the RepackageEvent and its paired
    REPACKAGE_OUT/REPACKAGE_IN StockMovement rows — all inside one
    atomic block, same as the original view.

    Callers are responsible for running RepackageCreateSerializer
    themselves first (same division of labour as record_sale() and
    record_stock_count() — this function assumes well-typed Decimal
    values) and for the IsOwnerOrManager permission check: this is a
    role-gated action live, and going offline must not become a way to
    bypass that gate, so the sync push handler enforces the same role
    check the live endpoint's permission_classes did before ever
    calling this.

    `sync_idempotency_key`, when given (only the sync push path passes
    one), makes this call safe to retry: if a RepackageEvent already
    exists with this key, it's returned as-is with no second write —
    mirrors record_sale()'s and record_stock_count()'s identical
    parameter and rationale exactly.

    Raises RepackageError for every condition the live view used to
    turn into an error Response (unit not found, mismatched product,
    wrong parent, insufficient stock), carrying the same message and
    status code. Returns the created (or, on a retried key, the
    already-existing) RepackageEvent — callers serialize it themselves.
    """
    if sync_idempotency_key:
        existing = RepackageEvent.objects.filter(
            business=business, sync_idempotency_key=sync_idempotency_key,
        ).first()
        if existing is not None:
            return existing

    try:
        from_unit = ProductUnit.objects.select_related('product').get(
            id=from_unit_id, product__business=business,
        )
    except ProductUnit.DoesNotExist:
        raise RepackageError(MESSAGES['REPACKAGE_FROM_UNIT_NOT_FOUND'], 404)

    try:
        to_unit = ProductUnit.objects.select_related('product', 'parent').get(
            id=to_unit_id, product__business=business,
        )
    except ProductUnit.DoesNotExist:
        raise RepackageError(MESSAGES['REPACKAGE_TO_UNIT_NOT_FOUND'], 404)

    # Same checks as RepackageEvent.clean() — done here first so a bad
    # pairing comes back as a normal 400 with a specific message rather
    # than a generic ValidationError from .full_clean() below.
    if from_unit.product_id != to_unit.product_id:
        raise RepackageError(MESSAGES['REPACKAGE_DIFFERENT_PRODUCTS'], 400)
    if not to_unit.is_repackaged:
        raise RepackageError(MESSAGES['REPACKAGE_TO_UNIT_NOT_REPACKAGED'], 400)
    if to_unit.parent_id != from_unit.id:
        raise RepackageError(MESSAGES['REPACKAGE_WRONG_PARENT'], 400)

    available = from_unit.available_quantity()
    if quantity_consumed > available:
        raise RepackageError(
            MESSAGES['REPACKAGE_INSUFFICIENT_STOCK'].format(
                unit=from_unit.get_unit_display(), available=available, requested=quantity_consumed,
            ),
            400,
        )

    # expected_yield/loss_quantity are stored at the ratio in effect
    # right now — see RepackageEvent's docstring for why this isn't
    # computed on read. A negative loss_quantity (produced more than
    # the theoretical yield) is left as-is rather than clamped to zero:
    # that's a real signal the ratio the owner entered is off and worth
    # surfacing, not hiding.
    expected_yield = (quantity_consumed * to_unit.ratio_to_parent).quantize(Decimal('0.001'))
    loss_quantity = (expected_yield - quantity_produced).quantize(Decimal('0.001'))

    try:
        with db_transaction.atomic():
            from_before = from_unit.available_quantity()
            from_unit.deduct_sale(quantity_consumed)
            from_after = from_unit.available_quantity()

            to_before = to_unit.stock_quantity
            to_unit.stock_quantity = to_unit.stock_quantity + quantity_produced
            to_unit.save(update_fields=['stock_quantity', 'updated_at'])

            event = RepackageEvent.objects.create(
                business=business,
                from_unit=from_unit,
                to_unit=to_unit,
                quantity_consumed=quantity_consumed,
                quantity_produced=quantity_produced,
                expected_yield=expected_yield,
                loss_quantity=loss_quantity,
                notes=notes,
                performed_by=user,
                sync_idempotency_key=sync_idempotency_key,
            )

            StockMovement.objects.create(
                business=business,
                product=from_unit.product,
                product_unit=from_unit,
                movement_type=StockMovement.MovementType.REPACKAGE_OUT,
                quantity_change=-quantity_consumed,
                quantity_before=from_before,
                quantity_after=from_after,
                notes=MESSAGES['STOCK_MOVEMENT_REPACKAGE_OUT_NOTE'].format(to_unit=to_unit.get_unit_display()),
                created_by=user,
            )
            StockMovement.objects.create(
                business=business,
                product=to_unit.product,
                product_unit=to_unit,
                movement_type=StockMovement.MovementType.REPACKAGE_IN,
                quantity_change=quantity_produced,
                quantity_before=to_before,
                quantity_after=to_unit.stock_quantity,
                notes=MESSAGES['STOCK_MOVEMENT_REPACKAGE_IN_NOTE'].format(from_unit=from_unit.get_unit_display()),
                created_by=user,
            )
    except IntegrityError:
        # Same race as record_sale()'s and record_stock_count()'s
        # identical guard: a concurrent retry of the exact same queued
        # operation won between our lookup above and this create() —
        # fetch and return that one rather than surfacing a spurious
        # failure. The atomic block means either everything above
        # committed or nothing did, so there's no partial-write case to
        # worry about here the way there could be if the event/movement
        # creates weren't wrapped together.
        if sync_idempotency_key:
            existing = RepackageEvent.objects.filter(
                business=business, sync_idempotency_key=sync_idempotency_key,
            ).first()
            if existing is not None:
                return existing
        raise

    return event
