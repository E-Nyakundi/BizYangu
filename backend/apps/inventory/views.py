"""
BizYangu — inventory views.
Stock levels, low-stock alerts, movement log, manual stock count.
"""

import logging
from decimal import Decimal
from django.db import transaction as db_transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwnerOrManager
from apps.catalog.models import Product, ProductUnit
from apps.core.messages import MESSAGES
from . import services
from .models import StockMovement, RepackageEvent
from .serializers import (
    StockMovementSerializer,
    StockCountSerializer,
    StockLevelSerializer,
    RepackageEventSerializer,
    RepackageCreateSerializer,
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


# ── Stock levels ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def stock_levels(request):
    """
    GET /api/v1/inventory/
    Current stock levels for all tracked products in the business.
    Supports ?q=search and ?category=id filters.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    qs = Product.objects.filter(
        business=business,
        is_active=True,
        track_stock=True,
    ).select_related('category').order_by('name')

    q = request.query_params.get('q', '').strip()
    if q:
        qs = qs.filter(name__icontains=q) | qs.filter(sku__icontains=q)

    category_id = request.query_params.get('category')
    if category_id:
        qs = qs.filter(category_id=category_id)

    serializer = StockLevelSerializer(qs, many=True)
    return Response(serializer.data)


# ── Low stock ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def low_stock(request):
    """
    GET /api/v1/inventory/low-stock/
    Products at or below their low_stock_threshold, plus out-of-stock.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    from django.db.models import F
    qs = Product.objects.filter(
        business=business,
        is_active=True,
        track_stock=True,
        current_stock__lte=F('low_stock_threshold'),
    ).select_related('category').order_by('current_stock', 'name')

    serializer = StockLevelSerializer(qs, many=True)
    return Response(serializer.data)


# ── Movement log ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def movement_list(request):
    """
    GET /api/v1/inventory/movements/
    Audit trail of all stock movements for the business.
    Supports ?product=id and ?type=SALE|RESTOCK|... filters.
    Paginated (50 per page).
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    qs = StockMovement.objects.filter(business=business).select_related(
        'product', 'created_by'
    ).order_by('-created_at')

    product_id = request.query_params.get('product')
    if product_id:
        qs = qs.filter(product_id=product_id)

    movement_type = request.query_params.get('type', '').upper()
    if movement_type and movement_type in dict(StockMovement.MovementType.choices):
        qs = qs.filter(movement_type=movement_type)

    # Simple manual pagination
    page_size = 50
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    offset = (page - 1) * page_size
    total = qs.count()
    qs = qs[offset:offset + page_size]

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': StockMovementSerializer(qs, many=True).data,
    })


# ── Manual stock count ────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def submit_stock_count(request):
    """
    POST /api/v1/inventory/count/
    Submit a physical stock count. Sets current_stock to counted_quantity
    and records a COUNT movement for the audit trail.
    Body: { product_id, counted_quantity, notes? }

    Thin wrapper around services.record_stock_count() (Phase 5
    offline-sync extraction) — shared with the sync push endpoint,
    which calls record_stock_count() directly with no request object.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = StockCountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        movement = services.record_stock_count(
            business,
            request.user,
            serializer.validated_data['product_id'],
            serializer.validated_data['counted_quantity'],
            serializer.validated_data.get('notes', ''),
        )
    except services.StockCountError as e:
        return Response({'detail': e.detail}, status=e.status_code)

    return Response(
        {
            'detail': MESSAGES['STOCK_COUNT_SUBMITTED'],
            'movement': StockMovementSerializer(movement).data,
        },
        status=status.HTTP_201_CREATED,
    )


# ── Repackaging (C10) ─────────────────────────────────────────────────────────
# Turns one physical form of a product into another — e.g. a 90kg bag
# scooped into gorogoro tins. Owner/manager only, same tier as stock-in
# and adjustments: this moves real stock, not just records a sale.

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def repackage_list_create(request):
    """
    GET  /api/v1/inventory/repackage/  — History of repackaging events.
         Supports ?product=id filter.
    POST /api/v1/inventory/repackage/  — Record a repackaging event.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    if request.method == 'GET':
        qs = RepackageEvent.objects.filter(business=business).select_related(
            'from_unit__product', 'to_unit', 'performed_by',
        ).order_by('-created_at')

        product_id = request.query_params.get('product')
        if product_id:
            qs = qs.filter(from_unit__product_id=product_id)

        return Response(RepackageEventSerializer(qs, many=True).data)

    serializer = RepackageCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        from_unit = ProductUnit.objects.select_related('product').get(
            id=data['from_unit_id'], product__business=business,
        )
    except ProductUnit.DoesNotExist:
        return Response({'detail': MESSAGES['REPACKAGE_FROM_UNIT_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    try:
        to_unit = ProductUnit.objects.select_related('product', 'parent').get(
            id=data['to_unit_id'], product__business=business,
        )
    except ProductUnit.DoesNotExist:
        return Response({'detail': MESSAGES['REPACKAGE_TO_UNIT_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    # Same checks as RepackageEvent.clean() — done here first so a bad
    # pairing comes back as a normal 400 with a specific message rather
    # than a generic ValidationError from .full_clean() below.
    if from_unit.product_id != to_unit.product_id:
        return Response({'detail': MESSAGES['REPACKAGE_DIFFERENT_PRODUCTS']}, status=status.HTTP_400_BAD_REQUEST)
    if not to_unit.is_repackaged:
        return Response({'detail': MESSAGES['REPACKAGE_TO_UNIT_NOT_REPACKAGED']}, status=status.HTTP_400_BAD_REQUEST)
    if to_unit.parent_id != from_unit.id:
        return Response({'detail': MESSAGES['REPACKAGE_WRONG_PARENT']}, status=status.HTTP_400_BAD_REQUEST)

    quantity_consumed = data['quantity_consumed']
    quantity_produced = data['quantity_produced']

    available = from_unit.available_quantity()
    if quantity_consumed > available:
        return Response(
            {
                'detail': MESSAGES['REPACKAGE_INSUFFICIENT_STOCK'].format(
                    unit=from_unit.get_unit_display(), available=available, requested=quantity_consumed,
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # expected_yield/loss_quantity are stored at the ratio in effect right
    # now — see RepackageEvent's docstring for why this isn't computed on
    # read. A negative loss_quantity (produced more than the theoretical
    # yield) is left as-is rather than clamped to zero: that's a real
    # signal the ratio the owner entered is off and worth surfacing, not
    # hiding.
    expected_yield = (quantity_consumed * to_unit.ratio_to_parent).quantize(Decimal('0.001'))
    loss_quantity = (expected_yield - quantity_produced).quantize(Decimal('0.001'))

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
            notes=data.get('notes', ''),
            performed_by=request.user,
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
            created_by=request.user,
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
            created_by=request.user,
        )

        # Built inside the atomic block, same fix as settle_payment() /
        # create_refund() / void_transaction() in transactions/views.py —
        # a missing MESSAGES key or serializer error here rolls the whole
        # repackage back instead of committing it silently behind a 500.
        response_payload = {
            'detail': MESSAGES['REPACKAGE_RECORDED'],
            'event': RepackageEventSerializer(event).data,
        }

    return Response(response_payload, status=status.HTTP_201_CREATED)


# Same rate-throttle tier as transactions/views.py's money/stock-moving
# endpoints — repackaging moves real stock quantities, worth the same
# protection as a sale or stock-in.
repackage_list_create.cls.throttle_scope = 'burst_write'