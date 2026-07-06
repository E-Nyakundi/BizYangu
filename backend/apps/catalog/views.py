"""
BizYangu — catalog views.
Products (CRUD + CSV import) and categories.
All scoped to the authenticated user's business.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsSameBusiness, IsNotExpired, IsOwnerOrManager
from apps.core.messages import MESSAGES
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductCreateSerializer,
    parse_product_csv,
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


# ── Categories ────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def category_list_create(request):
    """
    GET  /api/v1/catalog/categories/  — List categories for current business.
    POST /api/v1/catalog/categories/  — Create a category.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    if request.method == 'GET':
        cats = Category.objects.filter(business=business, is_active=True).order_by('name')
        return Response(CategorySerializer(cats, many=True).data)

    serializer = CategorySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    cat = serializer.save(business=business)
    return Response(CategorySerializer(cat).data, status=status.HTTP_201_CREATED)


# ── Products ──────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def product_list_create(request):
    """
    GET  /api/v1/catalog/products/  — List products (search, filter by category).
    POST /api/v1/catalog/products/  — Create a product.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    if request.method == 'GET':
        qs = Product.objects.filter(business=business, is_active=True).select_related('category')

        # Search by name or SKU
        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(sku__icontains=q)

        # Filter by category
        category_id = request.query_params.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)

        # Filter by stock status
        stock_filter = request.query_params.get('stock')
        if stock_filter == 'low':
            from django.db.models import F
            qs = qs.filter(current_stock__lte=F('low_stock_threshold'), current_stock__gt=0)
        elif stock_filter == 'out':
            qs = qs.filter(current_stock__lte=0)

        qs = qs.order_by('name')
        return Response(ProductSerializer(qs, many=True).data)

    # POST — create product
    serializer = ProductCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Validate category belongs to this business
    category = serializer.validated_data.get('category')
    if category and category.business_id != business.id:
        return Response(
            {'detail': MESSAGES['CATEGORY_WRONG_BUSINESS']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    product = serializer.save(business=business)
    return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsNotExpired])
def product_detail(request, product_id):
    """
    GET    /api/v1/catalog/products/{id}/  — Single product.
    PATCH  /api/v1/catalog/products/{id}/  — Update product.
    DELETE /api/v1/catalog/products/{id}/  — Soft delete.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        product = Product.objects.get(id=product_id, business=business, is_active=True)
    except Product.DoesNotExist:
        return Response(
            {'detail': MESSAGES['PRODUCT_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(ProductSerializer(product).data)

    if request.method == 'PATCH':
        serializer = ProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Block changing SKU directly
        serializer.validated_data.pop('sku', None)
        serializer.save()
        return Response(ProductSerializer(product).data)

    # DELETE — soft delete
    product.is_active = False
    product.save(update_fields=['is_active'])
    return Response({'detail': MESSAGES['PRODUCT_DELETED']}, status=status.HTTP_200_OK)


# ── CSV import ────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
@parser_classes([MultiPartParser, FormParser])
def product_csv_import(request):
    """
    POST /api/v1/catalog/products/import/
    Upload a CSV file to bulk-create products.
    Expected columns: name, selling_price, [category, cost_price, unit,
    current_stock, low_stock_threshold, barcode, track_stock]
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    csv_file = request.FILES.get('file')
    if not csv_file:
        return Response(
            {'detail': MESSAGES['CSV_FILE_REQUIRED']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not csv_file.name.endswith('.csv'):
        return Response(
            {'detail': MESSAGES['CSV_INVALID_FORMAT']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    MAX_SIZE_MB = 5
    if csv_file.size > MAX_SIZE_MB * 1024 * 1024:
        return Response(
            {'detail': MESSAGES['CSV_FILE_TOO_LARGE'].format(max_size=MAX_SIZE_MB)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = parse_product_csv(csv_file, business)

    response_status = status.HTTP_200_OK if result['imported'] > 0 else status.HTTP_400_BAD_REQUEST
    return Response(result, status=response_status)