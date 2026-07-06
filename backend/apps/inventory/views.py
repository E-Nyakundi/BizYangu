"""
BizYangu — inventory views.
Stock levels, low-stock alerts, movement log, manual stock count.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwnerOrManager
from apps.catalog.models import Product
from apps.core.messages import MESSAGES
from .models import StockMovement
from .serializers import StockMovementSerializer, StockCountSerializer, StockLevelSerializer

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
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = StockCountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    product_id = serializer.validated_data['product_id']
    counted_qty = serializer.validated_data['counted_quantity']
    notes = serializer.validated_data.get('notes', '')

    try:
        product = Product.objects.get(id=product_id, business=business, is_active=True)
    except Product.DoesNotExist:
        return Response(
            {'detail': MESSAGES['PRODUCT_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    qty_before = product.current_stock
    status_before = product.stock_status
    product.current_stock = counted_qty
    product.save(update_fields=['current_stock'])

    movement = StockMovement.objects.create(
        business=business,
        product=product,
        movement_type=StockMovement.MovementType.COUNT,
        quantity_change=counted_qty - qty_before,
        quantity_before=qty_before,
        quantity_after=counted_qty,
        notes=notes or MESSAGES['STOCK_COUNT_NOTE'].format(quantity=counted_qty),
        created_by=request.user,
    )

    status_after = product.stock_status
    if status_after in ('LOW', 'OUT') and status_after != status_before:
        try:
            from apps.notifications.services import notify_low_stock
            notify_low_stock(product, status_after)
        except Exception:
            logger.exception('Low-stock notification failed for product %s', product.id)

    return Response(
        {
            'detail': MESSAGES['STOCK_COUNT_SUBMITTED'],
            'movement': StockMovementSerializer(movement).data,
        },
        status=status.HTTP_201_CREATED,
    )