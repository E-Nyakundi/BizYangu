"""
BizYangu — transactions views.
Record sale, stock-in, adjustment, loss, refund, list, detail, void.
"""

import logging
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.db.models import Q, Sum, Count, Min, Max
from django.db.models.functions import Lower
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwnerOrManager, IsOwner
from apps.catalog.models import Product, ProductUnit
from apps.catalog.serializers import ProductCreateSerializer, ProductSerializer
from apps.core.messages import MESSAGES
from apps.inventory.models import StockMovement
from apps.reports.consumers import notify_dashboard
from .models import Transaction, TransactionItem
User = get_user_model()

from .serializers import (
    SaleCreateSerializer,
    StockInSerializer,
    AdjustmentSerializer,
    RefundCreateSerializer,
    TransactionSerializer,
    VoidSerializer,
    UnreconciledGroupSerializer,
    ResolveUnreconciledSerializer,
)

logger = logging.getLogger(__name__)


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )
    return business, None


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


# ── Sale ──────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def create_sale(request):
    """
    POST /api/v1/transactions/sale/
    Record a sale. Validates stock availability, creates Transaction + items,
    and deducts stock via signal (transactions/models.py post_save).
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = SaleCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Resolve products and check stock
    line_items = []
    total = Decimal('0.00')

    for item_data in data['items']:
        qty = item_data['quantity']

        if item_data.get('product_unit_id'):
            # Sale against one specific sellable form of a product (C10) —
            # a stick rather than the pack, a gorogoro rather than the bag.
            # product is derived from the unit itself; there's no separate
            # product_id on this shape (validated in the serializer).
            try:
                unit = ProductUnit.objects.select_related('product', 'parent').get(
                    id=item_data['product_unit_id'],
                    product__business=business,
                    product__is_active=True,
                )
            except ProductUnit.DoesNotExist:
                return Response(
                    {'detail': MESSAGES['PRODUCT_UNIT_NOT_FOUND']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not unit.is_sellable:
                return Response(
                    {'detail': MESSAGES['PRODUCT_UNIT_NOT_SELLABLE']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if unit.selling_price is None:
                return Response(
                    {'detail': MESSAGES['PRODUCT_UNIT_NO_SELLING_PRICE'].format(unit=unit.get_unit_display())},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            available = unit.available_quantity()
            if available < qty:
                return Response(
                    {
                        'detail': MESSAGES['PRODUCT_UNIT_INSUFFICIENT_STOCK'].format(
                            name=unit.product.name, unit=unit.get_unit_display(),
                            remaining=available, requested=qty,
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
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
            # Not-in-catalog item: no Product to resolve, no stock to check,
            # no StockMovement to create — it's just a name + price the
            # cashier typed in (sell/page.tsx addCustomToCart).
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
            return Response(
                {'detail': MESSAGES['PRODUCT_NOT_FOUND_WITH_ID'].format(product_id=item_data['product_id'])},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if product.track_stock and product.current_stock < qty:
            return Response(
                {
                    'detail': MESSAGES['INSUFFICIENT_STOCK_DETAIL'].format(
                        name=product.name, remaining=product.current_stock, requested=qty
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
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

    # ── Resolve split-payment breakdown (item D13) ──────────────────────
    # Every SALE gets a real cash/mpesa/credit breakdown now, not just a
    # payment_method tag. For single-method sales the full total goes into
    # the one matching column; MIXED is the only case where the client's
    # own numbers are used, and even then only after they're checked
    # against the server-computed total — never trust a client total.
    method = data['payment_method']
    if method == Transaction.PaymentMethod.MIXED:
        cash_amount = data.get('cash_amount') or Decimal('0.00')
        mpesa_amount = data.get('mpesa_amount') or Decimal('0.00')
        credit_amount = data.get('credit_amount') or Decimal('0.00')
        if (cash_amount + mpesa_amount + credit_amount) != total:
            return Response(
                {'detail': MESSAGES['MIXED_PAYMENT_AMOUNTS_MISMATCH'].format(total=total)},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        cash_amount = total if method == Transaction.PaymentMethod.CASH else Decimal('0.00')
        mpesa_amount = total if method == Transaction.PaymentMethod.MPESA else Decimal('0.00')
        credit_amount = total if method == Transaction.PaymentMethod.CREDIT else Decimal('0.00')

    # ── Resolve customer for the credit portion (item D16) ──────────────
    customer = None
    if credit_amount > 0:
        from apps.customers.models import Customer
        customer_id = data.get('customer_id')
        customer_name = data.get('customer_name', '').strip()
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id, business=business, is_active=True)
            except Customer.DoesNotExist:
                return Response(
                    {'detail': MESSAGES['CUSTOMER_NOT_FOUND']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif customer_name:
            customer_phone = data.get('customer_phone', '').strip()
            # Same get-or-create-by-phone shape the Creditors "Add
            # customer" flow uses — a repeat customer paying on credit
            # again shouldn't fork into a second ledger row just because
            # the cashier retyped their name slightly differently, as
            # long as the phone number matches.
            if customer_phone:
                customer, _ = Customer.objects.get_or_create(
                    business=business, phone=customer_phone,
                    defaults={'name': customer_name},
                )
            else:
                customer = Customer.objects.create(business=business, name=customer_name)
        else:
            return Response(
                {'detail': MESSAGES['CREDIT_CUSTOMER_REQUIRED']},
                status=status.HTTP_400_BAD_REQUEST,
            )

    with db_transaction.atomic():
        txn = Transaction.objects.create(
            business=business,
            type=Transaction.Type.SALE,
            total_amount=total,
            payment_method=data['payment_method'],
            cash_amount=cash_amount,
            mpesa_amount=mpesa_amount,
            credit_amount=credit_amount,
            customer=customer,
            # M-Pesa sales start PENDING — the STK push hasn't been sent yet,
            # let alone confirmed by the customer. The callback (or manual
            # reconciliation) flips this to CONFIRMED. Every other payment
            # method is confirmed on the spot since cash/credit/mixed have
            # no separate confirmation step.
            payment_status=(
                Transaction.PaymentStatus.PENDING
                if data['payment_method'] == Transaction.PaymentMethod.MPESA
                else Transaction.PaymentStatus.CONFIRMED
            ),
            mpesa_reference=data.get('mpesa_reference', ''),
            notes=data.get('notes', ''),
            created_by=request.user,
        )

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
            # Stock deduction happens via post_save signal in transactions/models.py
            # But the signal fires on Transaction.create, before items exist.
            # So we handle stock + movement manually here for correctness.
            # li['product'] is None for not-in-catalog items — nothing to
            # deduct or track for those, skip straight past.
            if li.get('product_unit'):
                # C10 sale-flow integration: deduct from whichever ancestor
                # in the unit tree actually holds the counter for this
                # pool (see ProductUnit.deduct_sale), not Product.current_stock
                # — that's a separate pool this branch never touches. No
                # low-stock notification here either: it's keyed off
                # Product.current_stock/low_stock_threshold, neither of
                # which changed for this line.
                unit = li['product_unit']
                counted_node, _ratio = unit._walk_to_counted_ancestor()
                qty_before = counted_node.stock_quantity
                unit.deduct_sale(li['quantity'])
                counted_node.refresh_from_db(fields=['stock_quantity'])
                StockMovement.objects.create(
                    business=business,
                    product=li['product'],
                    product_unit=unit,
                    transaction=txn,
                    movement_type=StockMovement.MovementType.SALE,
                    quantity_change=counted_node.stock_quantity - qty_before,
                    quantity_before=qty_before,
                    quantity_after=counted_node.stock_quantity,
                    created_by=request.user,
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
                    created_by=request.user,
                )
                _notify_if_crossed_threshold(li['product'], status_before)

    notify_dashboard(business.id, 'sale')

    from apps.reports.services import check_sale_milestones
    check_sale_milestones(business)

    return Response(
        TransactionSerializer(txn).data,
        status=status.HTTP_201_CREATED,
    )


# ── Stock in ──────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def create_stock_in(request):
    """
    POST /api/v1/transactions/stock-in/
    Record a stock delivery (increases product current_stock).
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = StockInSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        product = Product.objects.get(id=data['product_id'], business=business, is_active=True)
    except Product.DoesNotExist:
        return Response({'detail': MESSAGES['PRODUCT_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    qty = data['quantity']
    unit_price = data.get('unit_price') or product.cost_price or Decimal('0')

    with db_transaction.atomic():
        txn = Transaction.objects.create(
            business=business,
            type=Transaction.Type.STOCK_IN,
            total_amount=qty * unit_price,
            payment_method=Transaction.PaymentMethod.CASH,
            payment_status=Transaction.PaymentStatus.CONFIRMED,
            notes=data.get('notes', ''),
            created_by=request.user,
        )
        TransactionItem.objects.create(
            transaction=txn,
            product=product,
            quantity=qty,
            unit_price=unit_price,
            cost_price=unit_price,
            subtotal=qty * unit_price,
        )
        qty_before = product.current_stock
        product.current_stock += qty
        product.save(update_fields=['current_stock'])
        StockMovement.objects.create(
            business=business,
            product=product,
            transaction=txn,
            movement_type=StockMovement.MovementType.RESTOCK,
            quantity_change=qty,
            quantity_before=qty_before,
            quantity_after=product.current_stock,
            notes=data.get('notes', ''),
            created_by=request.user,
        )

    notify_dashboard(business.id, 'stock_in')

    return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


# ── Adjustment / Loss ──────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def create_adjustment(request):
    """
    POST /api/v1/transactions/adjustment/
    POST /api/v1/transactions/loss/
    Manual stock adjustment or loss record.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = AdjustmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        product = Product.objects.get(id=data['product_id'], business=business, is_active=True)
    except Product.DoesNotExist:
        return Response({'detail': MESSAGES['PRODUCT_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    qty_change = data['quantity_change']
    reason = data['reason']

    type_map = {
        'ADJUSTMENT': Transaction.Type.ADJUSTMENT,
        'LOSS': Transaction.Type.LOSS,
        'DAMAGE': Transaction.Type.LOSS,
    }
    movement_map = {
        'ADJUSTMENT': StockMovement.MovementType.ADJUSTMENT,
        'LOSS': StockMovement.MovementType.LOSS,
        'DAMAGE': StockMovement.MovementType.DAMAGE,
    }

    qty_before = product.current_stock
    status_before = product.stock_status
    new_qty = qty_before + qty_change
    if new_qty < 0:
        return Response(
            {'detail': MESSAGES['ADJUSTMENT_NEGATIVE_STOCK']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with db_transaction.atomic():
        txn = Transaction.objects.create(
            business=business,
            type=type_map.get(reason, Transaction.Type.ADJUSTMENT),
            total_amount=Decimal('0'),
            payment_method=Transaction.PaymentMethod.CASH,
            payment_status=Transaction.PaymentStatus.CONFIRMED,
            notes=data.get('notes', ''),
            created_by=request.user,
        )
        TransactionItem.objects.create(
            transaction=txn,
            product=product,
            quantity=abs(qty_change),
            unit_price=product.selling_price,
            cost_price=product.cost_price,
            subtotal=Decimal('0'),
        )
        product.current_stock = new_qty
        product.save(update_fields=['current_stock'])
        StockMovement.objects.create(
            business=business,
            product=product,
            transaction=txn,
            movement_type=movement_map.get(reason, StockMovement.MovementType.ADJUSTMENT),
            quantity_change=qty_change,
            quantity_before=qty_before,
            quantity_after=new_qty,
            notes=data.get('notes', ''),
            created_by=request.user,
        )
        _notify_if_crossed_threshold(product, status_before)

    notify_dashboard(business.id, 'adjustment')

    return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


# ── List & detail ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def transaction_list(request):
    """
    GET /api/v1/transactions/
    List transactions. Supports ?type=SALE&page=1 filters.
    Owner/manager see all transactions for the business. Cashiers see only
    their own — they should not see other cashiers' sales totals.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    qs = Transaction.objects.filter(business=business, is_voided=False).order_by('-created_at')

    if request.user.role not in (User.Role.OWNER, User.Role.MANAGER):
        qs = qs.filter(created_by=request.user)

    txn_type = request.query_params.get('type', '').upper()
    if txn_type in dict(Transaction.Type.choices):
        qs = qs.filter(type=txn_type)

    payment = request.query_params.get('payment', '').upper()
    if payment in dict(Transaction.PaymentMethod.choices):
        qs = qs.filter(payment_method=payment)

    # Date filter: ?date=2026-06-26
    date_str = request.query_params.get('date')
    if date_str:
        try:
            from datetime import date
            d = date.fromisoformat(date_str)
            qs = qs.filter(created_at__date=d)
        except ValueError:
            pass

    page_size = 50
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    offset = (page - 1) * page_size
    total = qs.count()
    # select_related('created_by'): TransactionSerializer.created_by_name
    # reads created_by.name — without this it's one extra query per row
    # (50/page). annotate(refunded_total=...): TransactionSerializer used
    # to compute this with a fresh .aggregate() call per object in
    # get_refunded_amount — also one query per row. Both were real N+1s on
    # this endpoint; annotating/select_related here means the whole page
    # loads in a fixed number of queries regardless of page size.
    qs = (
        qs.select_related('created_by')
        .prefetch_related('items__product')
        .annotate(
            refunded_total=Sum(
                'refunds__total_amount',
                filter=Q(refunds__is_voided=False),
            )
        )[offset:offset + page_size]
    )

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': TransactionSerializer(qs, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def transaction_detail(request, transaction_id):
    """GET /api/v1/transactions/{id}/"""
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        txn = (
            Transaction.objects.select_related('created_by')
            .prefetch_related('items__product')
            .annotate(
                refunded_total=Sum(
                    'refunds__total_amount',
                    filter=Q(refunds__is_voided=False),
                )
            )
            .get(id=transaction_id, business=business)
        )
    except Transaction.DoesNotExist:
        return Response(
            {'detail': MESSAGES['TRANSACTION_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(TransactionSerializer(txn).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def receipt_lookup(request, reference_number):
    """
    GET /api/v1/transactions/receipt/{reference_number}/

    Item D12 — the "real, scannable receipt" fix. Resolves a printed/QR'd
    reference_number (e.g. BY-2026-0042) back to the full transaction.

    Scoped internally: authenticated + business-scoped, same as every
    other endpoint here. reference_number is only unique *within* a
    business (see the UniqueConstraint comment in models.py), so this
    can never leak another business's transaction even if two businesses
    happen to share a reference_number — the business filter makes that
    impossible to collide against. This is deliberately not a public,
    unauthenticated endpoint yet — see the pre-pilot doc's Architecture
    Principles section (#3) for why: build the internal lookup now,
    keep it structured so a public-safe view can read from the same
    source later without a rework, but don't build the public layer
    before there's an actual public consumer (the future Customer
    Platform) to justify it.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        txn = (
            Transaction.objects.select_related('created_by', 'customer')
            .prefetch_related('items__product')
            .annotate(
                refunded_total=Sum(
                    'refunds__total_amount',
                    filter=Q(refunds__is_voided=False),
                )
            )
            .get(business=business, reference_number=reference_number.strip().upper())
        )
    except Transaction.DoesNotExist:
        return Response(
            {'detail': MESSAGES['RECEIPT_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(TransactionSerializer(txn).data)


# ── Refund ────────────────────────────────────────────────────────────────────

def _apportion_refund_amount(original, amount):
    """
    Given a SALE Transaction and a KES amount to refund, splits that amount
    across the sale's line items proportional to each item's remaining
    refundable value. This exists purely so stock can be restored accurately
    per product — the split is never shown to the user, who only ever enters
    a plain amount. Returns a list of {original_item, quantity, subtotal}
    dicts, or None if the sale has nothing left to refund.
    """
    candidates = []
    total_remaining_value = Decimal('0.00')

    for item in original.items.all():
        already_refunded_qty = item.refund_items.filter(
            transaction__is_voided=False,
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        remaining_qty = item.quantity - already_refunded_qty
        remaining_value = (remaining_qty * item.unit_price).quantize(Decimal('0.01'))
        if remaining_value > 0:
            candidates.append({'item': item, 'remaining_qty': remaining_qty, 'remaining_value': remaining_value})
            total_remaining_value += remaining_value

    if total_remaining_value <= 0 or amount > total_remaining_value:
        return None

    lines = []
    allocated_total = Decimal('0.00')
    for entry in candidates:
        item = entry['item']
        share = (amount * entry['remaining_value'] / total_remaining_value).quantize(Decimal('0.01'))
        qty = (share / item.unit_price).quantize(Decimal('0.001')) if item.unit_price else Decimal('0')
        if qty > entry['remaining_qty']:
            qty = entry['remaining_qty']
            share = (qty * item.unit_price).quantize(Decimal('0.01'))
        if qty <= 0:
            continue
        lines.append({'original_item': item, 'quantity': qty, 'subtotal': share})
        allocated_total += share

    # Rounding across lines can leave the sum a cent or two off the amount
    # the user actually typed — nudge the largest line so the refund
    # transaction's total matches exactly what they entered.
    leftover = (amount - allocated_total).quantize(Decimal('0.01'))
    if leftover != 0 and lines:
        biggest = max(lines, key=lambda l: l['subtotal'])
        biggest['subtotal'] = (biggest['subtotal'] + leftover).quantize(Decimal('0.01'))

    return lines


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def create_refund(request):
    """
    POST /api/v1/transactions/refund/
    Body: { transaction_id, amount, reason }

    Amount-only refund: the cashier/owner types the KES amount handed back
    to the customer, nothing about which items. Distinct from void: the
    original sale stays exactly as it was — it's real revenue that
    happened — and this creates a separate type=REFUND Transaction linked
    via original_transaction, apportions + restores stock internally, and
    leaves the sale's own payment_status untouched. Supports partial
    refunds and repeated partial refunds on the same sale — how much is
    still refundable is computed from every prior non-voided refund
    against it.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = RefundCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        original = Transaction.objects.prefetch_related('items__product', 'items__product_unit').get(
            id=data['transaction_id'], business=business,
        )
    except Transaction.DoesNotExist:
        return Response({'detail': MESSAGES['TRANSACTION_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    if original.type != Transaction.Type.SALE:
        return Response({'detail': MESSAGES['REFUND_ORIGINAL_NOT_SALE']}, status=status.HTTP_400_BAD_REQUEST)
    if original.is_voided:
        return Response({'detail': MESSAGES['REFUND_ORIGINAL_VOIDED']}, status=status.HTTP_400_BAD_REQUEST)
    if original.payment_status != Transaction.PaymentStatus.CONFIRMED:
        return Response({'detail': MESSAGES['REFUND_ORIGINAL_NOT_CONFIRMED']}, status=status.HTTP_400_BAD_REQUEST)

    already_refunded_total = original.refunds.filter(is_voided=False).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')
    remaining_amount = (original.total_amount - already_refunded_total).quantize(Decimal('0.01'))

    amount = data['amount']
    if amount > remaining_amount:
        return Response(
            {'detail': MESSAGES['REFUND_AMOUNT_EXCEEDS_REMAINING'].format(amount=amount, remaining=remaining_amount)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lines = _apportion_refund_amount(original, amount)
    if lines is None:
        return Response(
            {'detail': MESSAGES['REFUND_AMOUNT_EXCEEDS_REMAINING'].format(amount=amount, remaining=remaining_amount)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with db_transaction.atomic():
        refund_txn = Transaction.objects.create(
            business=business,
            type=Transaction.Type.REFUND,
            original_transaction=original,
            total_amount=amount,
            payment_method=original.payment_method,
            payment_status=Transaction.PaymentStatus.CONFIRMED,
            notes=data['reason'],
            created_by=request.user,
        )

        for line in lines:
            original_item = line['original_item']
            TransactionItem.objects.create(
                transaction=refund_txn,
                product=original_item.product,
                product_unit=original_item.product_unit,
                name=original_item.name,
                is_reconciled=original_item.is_reconciled,
                quantity=line['quantity'],
                unit_price=original_item.unit_price,
                cost_price=original_item.cost_price,
                subtotal=line['subtotal'],
                original_item=original_item,
            )

            # original_item.product is None for a refund against a
            # not-in-catalog sale line — nothing was deducted at sale time,
            # so there's no stock to restore here either.
            product = original_item.product
            if original_item.product_unit_id:
                # C10: the sale deducted from the unit tree's own pool
                # (ProductUnit.deduct_sale), not Product.current_stock —
                # restore that same pool via ProductUnit.restore_sale, not
                # the branch below.
                unit = original_item.product_unit
                counted_node, _ratio = unit._walk_to_counted_ancestor()
                qty_before = counted_node.stock_quantity
                unit.restore_sale(line['quantity'])
                counted_node.refresh_from_db(fields=['stock_quantity'])
                StockMovement.objects.create(
                    business=business,
                    product=product,
                    product_unit=unit,
                    transaction=refund_txn,
                    movement_type=StockMovement.MovementType.REFUND,
                    quantity_change=counted_node.stock_quantity - qty_before,
                    quantity_before=qty_before,
                    quantity_after=counted_node.stock_quantity,
                    notes=MESSAGES['STOCK_MOVEMENT_REFUND_NOTE'].format(reference=original.reference_number),
                    created_by=request.user,
                )
            elif product and product.track_stock:
                qty_before = product.current_stock
                product.current_stock += line['quantity']
                product.save(update_fields=['current_stock'])
                StockMovement.objects.create(
                    business=business,
                    product=product,
                    transaction=refund_txn,
                    movement_type=StockMovement.MovementType.REFUND,
                    quantity_change=line['quantity'],
                    quantity_before=qty_before,
                    quantity_after=product.current_stock,
                    notes=MESSAGES['STOCK_MOVEMENT_REFUND_NOTE'].format(reference=original.reference_number),
                    created_by=request.user,
                )

        # Built inside the atomic block so a future missing MESSAGES key or
        # serializer error rolls the refund back instead of committing it
        # silently behind a 500 — same fix applied to settle_payment()
        # after that exact failure mode hit production (see its comment).
        response_payload = {
            'detail': MESSAGES['REFUND_PROCESSED'],
            'transaction': TransactionSerializer(refund_txn).data,
        }

    notify_dashboard(business.id, 'refund')

    return Response(response_payload, status=status.HTTP_201_CREATED)


# ── Void ──────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def void_transaction(request, transaction_id):
    """
    POST /api/v1/transactions/{id}/void/
    Void a transaction. Restores stock for SALE transactions.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        txn = Transaction.objects.prefetch_related('items__product', 'items__product_unit').get(
            id=transaction_id, business=business
        )
    except Transaction.DoesNotExist:
        return Response(
            {'detail': MESSAGES['TRANSACTION_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    if txn.is_voided:
        return Response(
            {'detail': MESSAGES['TRANSACTION_ALREADY_VOIDED']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = VoidSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    with db_transaction.atomic():
        txn.is_voided = True
        txn.void_reason = serializer.validated_data['reason']
        txn.void_by = request.user
        txn.save(update_fields=['is_voided', 'void_reason', 'void_by'])

        # Restore stock for SALE transactions
        if txn.type == Transaction.Type.SALE:
            for item in txn.items.all():
                # item.product is None for not-in-catalog items — nothing
                # was deducted for those at sale time, so nothing to restore.
                if item.product_unit_id:
                    # C10: this line was sold against a specific sellable
                    # form, so the sale deducted from the unit tree's own
                    # pool, not Product.current_stock — restore that same
                    # pool via ProductUnit.restore_sale instead.
                    unit = item.product_unit
                    counted_node, _ratio = unit._walk_to_counted_ancestor()
                    qty_before = counted_node.stock_quantity
                    unit.restore_sale(item.quantity)
                    counted_node.refresh_from_db(fields=['stock_quantity'])
                    StockMovement.objects.create(
                        business=business,
                        product=item.product,
                        product_unit=unit,
                        transaction=txn,
                        movement_type=StockMovement.MovementType.REFUND,
                        quantity_change=counted_node.stock_quantity - qty_before,
                        quantity_before=qty_before,
                        quantity_after=counted_node.stock_quantity,
                        notes=MESSAGES['STOCK_MOVEMENT_REFUND_NOTE'].format(reference=txn.reference_number),
                        created_by=request.user,
                    )
                elif item.product and item.product.track_stock:
                    qty_before = item.product.current_stock
                    item.product.current_stock += item.quantity
                    item.product.save(update_fields=['current_stock'])
                    StockMovement.objects.create(
                        business=business,
                        product=item.product,
                        transaction=txn,
                        movement_type=StockMovement.MovementType.REFUND,
                        quantity_change=item.quantity,
                        quantity_before=qty_before,
                        quantity_after=item.product.current_stock,
                        notes=MESSAGES['STOCK_MOVEMENT_REFUND_NOTE'].format(reference=txn.reference_number),
                        created_by=request.user,
                    )

        # Same fix as settle_payment() and create_refund() — built inside
        # the atomic block so a future missing MESSAGES key or serializer
        # error rolls the void back instead of committing it silently
        # behind a 500.
        response_payload = {
            'detail': MESSAGES['TRANSACTION_VOIDED'],
            'transaction': TransactionSerializer(txn).data,
        }

    notify_dashboard(business.id, 'void')

    return Response(response_payload, status=status.HTTP_200_OK)


# ── Reconciliation queue (Phase 9.2, minimal — pilot-path plan Phase 2) ────────
# Closes the loop on Phase 9.1: a sale can include a not-in-catalog
# ("custom") item — {name, unit_price} with no product_id — so a cashier
# is never blocked from ringing up something that isn't set up yet. But
# until now nothing ever turned that into real catalog/stock data, so
# stock counts silently drifted for any business that used the feature.
# These two endpoints are deliberately minimal: exact-name grouping, no
# fuzzy matching, no taxonomy suggestions (that's Phase 9.5/Phase 4 of
# the pilot-path plan) — just "don't let unreconciled sales be a dead end."

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def unreconciled_list(request):
    """
    GET /api/v1/transactions/unreconciled/
    Every not-yet-resolved custom sale item, grouped by the freeform name
    the cashier typed at sale time (case-insensitive) — five separate
    sales of "Blue Band 500g" become one queue entry with item_count=5,
    not five rows. Owner/manager only, same tier as stock-in/adjustment.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    grouped = (
        TransactionItem.objects
        .filter(transaction__business=business, is_reconciled=False, product__isnull=True)
        .annotate(name_key=Lower('name'))
        .values('name_key')
        .annotate(
            display_name=Max('name'),  # arbitrary stable pick for casing shown to the owner
            item_count=Count('id'),
            total_quantity=Sum('quantity'),
            total_value=Sum('subtotal'),
            first_sold_at=Min('transaction__created_at'),
            last_sold_at=Max('transaction__created_at'),
        )
        .order_by('-last_sold_at')
    )

    results = [
        {
            'name': row['display_name'],
            'item_count': row['item_count'],
            'total_quantity': row['total_quantity'],
            'total_value': row['total_value'],
            'first_sold_at': row['first_sold_at'],
            'last_sold_at': row['last_sold_at'],
        }
        for row in grouped
    ]
    return Response(UnreconciledGroupSerializer(results, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def unreconciled_resolve(request):
    """
    POST /api/v1/transactions/unreconciled/resolve/
    Body: { name, product_id } — link every unreconciled item matching
    `name` to an existing catalog product, or
    { name, new_product: {...} } — create a new product from the queue
    entry (validated the same way as adding a product by hand) and link
    to that instead.

    Deliberately does NOT touch current_stock. Those units were sold
    before the product existed in the catalog — there's no "stock
    before" to add back, unlike a void/refund. This purely links the
    historical sale rows to a real product so reports and product
    performance start counting them from here on; reports/views.py
    already excludes items with product_id null, so no reporting change
    was needed for this to work correctly.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = ResolveUnreconciledSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    items = TransactionItem.objects.filter(
        transaction__business=business,
        is_reconciled=False,
        product__isnull=True,
        name__iexact=data['name'],
    )
    if not items.exists():
        return Response(
            {'detail': MESSAGES['UNRECONCILED_GROUP_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    if data.get('product_id'):
        try:
            product = Product.objects.get(id=data['product_id'], business=business, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {'detail': MESSAGES['PRODUCT_NOT_FOUND_WITH_ID'].format(product_id=data['product_id'])},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        new_product_data = dict(data['new_product'])
        new_product_data.setdefault('name', data['name'])
        product_serializer = ProductCreateSerializer(data=new_product_data)
        product_serializer.is_valid(raise_exception=True)
        category = product_serializer.validated_data.get('category')
        if category and category.business_id != business.id:
            return Response(
                {'detail': MESSAGES['CATEGORY_WRONG_BUSINESS']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        product = product_serializer.save(business=business, created_via=Product.CreationSource.RECONCILIATION)

    with db_transaction.atomic():
        resolved_count = items.update(product=product, is_reconciled=True)

    notify_dashboard(business.id, 'reconcile')

    from apps.reports.services import check_catalog_milestones
    check_catalog_milestones(business)

    return Response({
        'product': ProductSerializer(product).data,
        'resolved_count': resolved_count,
    }, status=status.HTTP_200_OK)


# ── Throttle scoping ──────────────────────────────────────────────────────
# @api_view wraps these into a class accessible via `.cls` — this is the
# standard DRF pattern for attaching a ScopedRateThrottle scope to a
# function-based view. 'burst_write' (30/min, see REST_FRAMEWORK in
# settings/base.py) sits on top of the general per-user rate, specifically
# on the endpoints that move money or stock — the ones worth protecting
# even from a single legitimate but malfunctioning client (e.g. a retry
# loop on a flaky connection hammering /transactions/sale/).
for _view in (create_sale, create_stock_in, create_adjustment, create_refund, void_transaction, unreconciled_resolve):
    _view.cls.throttle_scope = 'burst_write'