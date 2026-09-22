"""
BizYangu — transactions services.

record_sale() holds the actual sale-recording logic, extracted out of
views.create_sale() so it can be called from two places with identical
behaviour: the live HTTP endpoint, and the offline-sync push endpoint
(apps.sync.views), which has no real DRF `request` to hand a view — a
device batches up sales made while offline and replays them once it
regains connectivity, each one needing the exact same validation, stock
deduction, and notification side effects a normal live sale gets.

Raises SaleError for every validation-style failure that used to return
a Response directly from the view. The view catches this and turns it
into the same {'detail': ...} 400 response as before; the sync push
endpoint catches it and turns it into that operation's per-record
failure entry, without affecting any other operation in the same batch.
"""

import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.utils import IntegrityError

from apps.catalog.models import Product, ProductUnit
from apps.core.messages import MESSAGES
from apps.inventory.models import StockMovement
from apps.reports.consumers import notify_dashboard
from .models import Transaction, TransactionItem

logger = logging.getLogger(__name__)


class SaleError(Exception):
    """
    Raised for any validation-style failure in record_sale() — the same
    conditions that used to short-circuit create_sale() with a 400
    Response. Carries the same user-facing message so both call sites
    (the live view, the sync push endpoint) can surface it unchanged.
    """
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _notify_if_crossed_threshold(product, status_before: str) -> None:
    """
    Fires a push notification only on the transition INTO a worse stock
    state (OK→LOW, OK→OUT, LOW→OUT) — never repeats for every sale once
    a product is already sitting at LOW or OUT. Swallows any error;
    a failed push must never roll back or fail the transaction that
    triggered it.
    """
    status_after = product.stock_status
    if status_after in ('LOW', 'OUT') and status_after != status_before:
        try:
            from apps.notifications.services import notify_low_stock
            notify_low_stock(product, status_after)
        except Exception:
            logger.exception('Low-stock notification failed for product %s', product.id)


class StockInError(Exception):
    """
    Raised for any validation-style failure in record_stock_in() — the
    same conditions that used to short-circuit create_stock_in() with a
    Response. Carries the same user-facing message and status code the
    original view returned, mirroring SaleError/StockCountError's exact
    shape so all three call sites (view + sync push handler, per
    service) behave identically to their pre-extraction selves.
    """
    def __init__(self, detail, status_code=400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def record_stock_in(business, user, product_id, quantity, unit_price=None, notes='', sync_idempotency_key=None):
    """
    Records a stock delivery: creates a STOCK_IN Transaction + its
    single TransactionItem, increases the product's current_stock, and
    logs a RESTOCK StockMovement — exactly as views.create_stock_in
    always has.

    Extracted out of the view for the same reason record_sale() and
    record_stock_count() were: the offline-sync push endpoint
    (apps.sync.views) has no real DRF request to hand a view, but a
    device that received a delivery while offline needs the exact same
    validation, stock write, and notification side effects a live
    stock-in gets.

    Callers are responsible for running StockInSerializer themselves
    first (same division of labour as record_sale/record_stock_count)
    and for the IsOwnerOrManager permission check: stock-in is
    role-gated live, and going offline must not become a way around
    that gate, so the sync push handler enforces the same role check
    the live endpoint's permission_classes did before ever calling
    this.

    `sync_idempotency_key`, when given (only the sync push path passes
    one), makes this call safe to retry: if a Transaction already
    exists with this key, it's returned as-is with no second delivery
    recorded and no stock double-counted — mirrors record_sale()'s
    identical parameter and rationale exactly.

    Raises StockInError (404) if the product doesn't exist, is
    inactive, or belongs to a different business. Returns the created
    (or, on a retried key, the already-existing) Transaction — callers
    serialize it themselves.
    """
    if sync_idempotency_key:
        existing = Transaction.objects.filter(
            business=business, sync_idempotency_key=sync_idempotency_key,
        ).first()
        if existing is not None:
            return existing

    try:
        product = Product.objects.get(id=product_id, business=business, is_active=True)
    except Product.DoesNotExist:
        raise StockInError(MESSAGES['PRODUCT_NOT_FOUND'], 404)

    resolved_unit_price = unit_price if unit_price is not None else (product.cost_price or Decimal('0'))

    try:
        with db_transaction.atomic():
            txn = Transaction.objects.create(
                business=business,
                type=Transaction.Type.STOCK_IN,
                total_amount=quantity * resolved_unit_price,
                payment_method=Transaction.PaymentMethod.CASH,
                payment_status=Transaction.PaymentStatus.CONFIRMED,
                notes=notes,
                created_by=user,
                sync_idempotency_key=sync_idempotency_key,
            )
            TransactionItem.objects.create(
                transaction=txn,
                product=product,
                quantity=quantity,
                unit_price=resolved_unit_price,
                cost_price=resolved_unit_price,
                subtotal=quantity * resolved_unit_price,
            )
            qty_before = product.current_stock
            product.current_stock += quantity
            product.save(update_fields=['current_stock'])
            StockMovement.objects.create(
                business=business,
                product=product,
                transaction=txn,
                movement_type=StockMovement.MovementType.RESTOCK,
                quantity_change=quantity,
                quantity_before=qty_before,
                quantity_after=product.current_stock,
                notes=notes,
                created_by=user,
                sync_idempotency_key=sync_idempotency_key,
            )
    except IntegrityError:
        # Same race as record_sale()'s / record_stock_count()'s
        # identical guard: a concurrent retry of the exact same queued
        # operation won between our lookup above and this create() —
        # fetch and return that one rather than surfacing a spurious
        # failure.
        if sync_idempotency_key:
            existing = Transaction.objects.filter(
                business=business, sync_idempotency_key=sync_idempotency_key,
            ).first()
            if existing is not None:
                return existing
        raise

    notify_dashboard(business.id, 'stock_in')

    return txn


def record_sale(business, user, data, sync_idempotency_key=None):
    """
    Create a SALE Transaction + its TransactionItems, deduct stock, and
    fire the usual dashboard/notification side effects.

    `data` is the already-validated output of SaleCreateSerializer —
    both call sites (the view, sync push) are responsible for running
    that serializer themselves first, so this function can assume
    well-typed values and focus purely on business rules.

    `sync_idempotency_key`, when given (only the sync push path passes
    one — the live view never does), makes this call safe to retry: if
    a Transaction already exists with this key, it's returned as-is
    with no new sale created, no stock touched a second time, and no
    duplicate notification fired. This is what makes it safe for a
    device to retry a push whose response it never received.

    Raises SaleError for anything that used to be a 400 Response:
    unknown product/unit, insufficient stock, mismatched split-payment
    amounts, missing credit customer info. Returns the created (or, on
    a retried key, the already-existing) Transaction — callers
    serialize it themselves, since the live view and the sync push
    endpoint want different response shapes around it.
    """
    if sync_idempotency_key:
        existing = Transaction.objects.filter(
            business=business, sync_idempotency_key=sync_idempotency_key,
        ).first()
        if existing is not None:
            return existing

    line_items = []
    total = Decimal('0.00')

    for item_data in data['items']:
        qty = item_data['quantity']

        if item_data.get('product_unit_id'):
            try:
                unit = ProductUnit.objects.select_related('product', 'parent').get(
                    id=item_data['product_unit_id'],
                    product__business=business,
                    product__is_active=True,
                )
            except ProductUnit.DoesNotExist:
                raise SaleError(MESSAGES['PRODUCT_UNIT_NOT_FOUND'])

            if not unit.is_sellable:
                raise SaleError(MESSAGES['PRODUCT_UNIT_NOT_SELLABLE'])

            if unit.selling_price is None:
                raise SaleError(
                    MESSAGES['PRODUCT_UNIT_NO_SELLING_PRICE'].format(unit=unit.get_unit_display())
                )

            available = unit.available_quantity()
            if available < qty:
                raise SaleError(
                    MESSAGES['PRODUCT_UNIT_INSUFFICIENT_STOCK'].format(
                        name=unit.product.name, unit=unit.get_unit_display(),
                        remaining=available, requested=qty,
                    )
                )

            subtotal = qty * unit.selling_price
            total += subtotal
            line_items.append({
                'product': unit.product,
                'product_unit': unit,
                'name': '',
                'is_reconciled': True,
                'quantity': qty,
                'unit_price': unit.selling_price,
                'cost_price': unit.product.cost_price,
                'subtotal': subtotal,
            })
            continue

        if not item_data.get('product_id'):
            subtotal = qty * item_data['unit_price']
            total += subtotal
            line_items.append({
                'product': None,
                'product_unit': None,
                'name': item_data['name'],
                'is_reconciled': False,
                'quantity': qty,
                'unit_price': item_data['unit_price'],
                'cost_price': None,
                'subtotal': subtotal,
            })
            continue

        try:
            product = Product.objects.get(
                id=item_data['product_id'],
                business=business,
                is_active=True,
            )
        except Product.DoesNotExist:
            raise SaleError(MESSAGES['PRODUCT_NOT_FOUND_WITH_ID'].format(product_id=item_data['product_id']))

        if product.track_stock and product.current_stock < qty:
            raise SaleError(
                MESSAGES['INSUFFICIENT_STOCK_DETAIL'].format(
                    name=product.name, remaining=product.current_stock, requested=qty
                )
            )

        subtotal = qty * product.selling_price
        total += subtotal
        line_items.append({
            'product': product,
            'product_unit': None,
            'name': '',
            'is_reconciled': True,
            'quantity': qty,
            'unit_price': product.selling_price,
            'cost_price': product.cost_price,
            'subtotal': subtotal,
        })

    method = data['payment_method']
    if method == Transaction.PaymentMethod.MIXED:
        cash_amount = data.get('cash_amount') or Decimal('0.00')
        mpesa_amount = data.get('mpesa_amount') or Decimal('0.00')
        credit_amount = data.get('credit_amount') or Decimal('0.00')
        if (cash_amount + mpesa_amount + credit_amount) != total:
            raise SaleError(MESSAGES['MIXED_PAYMENT_AMOUNTS_MISMATCH'].format(total=total))
    else:
        cash_amount = total if method == Transaction.PaymentMethod.CASH else Decimal('0.00')
        mpesa_amount = total if method == Transaction.PaymentMethod.MPESA else Decimal('0.00')
        credit_amount = total if method == Transaction.PaymentMethod.CREDIT else Decimal('0.00')

    customer = None
    if credit_amount > 0:
        from apps.customers.models import Customer
        customer_id = data.get('customer_id')
        customer_name = data.get('customer_name', '').strip()
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id, business=business, is_active=True)
            except Customer.DoesNotExist:
                raise SaleError(MESSAGES['CUSTOMER_NOT_FOUND'])
        elif customer_name:
            customer_phone = data.get('customer_phone', '').strip()
            if customer_phone:
                customer, _ = Customer.objects.get_or_create(
                    business=business, phone=customer_phone,
                    defaults={'name': customer_name},
                )
            else:
                customer = Customer.objects.create(business=business, name=customer_name)
        else:
            raise SaleError(MESSAGES['CREDIT_CUSTOMER_REQUIRED'])

    with db_transaction.atomic():
        try:
            txn = Transaction.objects.create(
                business=business,
                type=Transaction.Type.SALE,
                total_amount=total,
                payment_method=data['payment_method'],
                cash_amount=cash_amount,
                mpesa_amount=mpesa_amount,
                credit_amount=credit_amount,
                customer=customer,
                payment_status=(
                    Transaction.PaymentStatus.PENDING
                    if data['payment_method'] == Transaction.PaymentMethod.MPESA
                    else Transaction.PaymentStatus.CONFIRMED
                ),
                mpesa_reference=data.get('mpesa_reference', ''),
                notes=data.get('notes', ''),
                created_by=user,
                sync_idempotency_key=sync_idempotency_key,
            )
        except IntegrityError:
            # Only reachable via the sync_idempotency_key unique
            # constraint (every other field here is either unconstrained
            # or has its own uniqueness handled by
            # Transaction._generate_reference's row lock). Means a
            # concurrent retry of the exact same queued operation won the
            # race and already created this sale between our lookup above
            # and this create() — fetch and return that one instead of
            # surfacing a spurious failure for what is, from the device's
            # perspective, the sale it already successfully recorded.
            if sync_idempotency_key:
                existing = Transaction.objects.filter(
                    business=business, sync_idempotency_key=sync_idempotency_key,
                ).first()
                if existing is not None:
                    return existing
            raise

        for li in line_items:
            TransactionItem.objects.create(
                transaction=txn,
                product=li['product'],
                product_unit=li.get('product_unit'),
                name=li['name'],
                is_reconciled=li['is_reconciled'],
                quantity=li['quantity'],
                unit_price=li['unit_price'],
                cost_price=li['cost_price'],
                subtotal=li['subtotal'],
            )
            if li.get('product_unit'):
                unit = li['product_unit']
                qty_before, qty_after = unit.deduct_sale(li['quantity'])
                StockMovement.objects.create(
                    business=business,
                    product=li['product'],
                    product_unit=unit,
                    transaction=txn,
                    movement_type=StockMovement.MovementType.SALE,
                    quantity_change=qty_after - qty_before,
                    quantity_before=qty_before,
                    quantity_after=qty_after,
                    created_by=user,
                )
            elif li['product'] and li['product'].track_stock:
                qty_before = li['product'].current_stock
                status_before = li['product'].stock_status
                qty_after = qty_before - li['quantity']
                li['product'].current_stock = qty_after
                li['product'].save(update_fields=['current_stock'])
                StockMovement.objects.create(
                    business=business,
                    product=li['product'],
                    transaction=txn,
                    movement_type=StockMovement.MovementType.SALE,
                    quantity_change=-li['quantity'],
                    quantity_before=qty_before,
                    quantity_after=qty_after,
                    created_by=user,
                )
                _notify_if_crossed_threshold(li['product'], status_before)

    notify_dashboard(business.id, 'sale')

    from apps.reports.services import check_sale_milestones
    check_sale_milestones(business)

    return txn
