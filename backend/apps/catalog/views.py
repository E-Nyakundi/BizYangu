"""
BizYangu — catalog views.
Products (CRUD + CSV import) and categories.
All scoped to the authenticated user's business.
"""

import logging
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsSameBusiness, IsNotExpired, IsOwnerOrManager
from apps.core.messages import MESSAGES
from .models import Category, Product, ProductUnit, get_fixed_ratio
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductCreateSerializer,
    ProductUnitSerializer,
    ProductUnitWriteSerializer,
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

    # Find-or-create by name when no category id was given but a name
    # was — the path taxonomy-driven onboarding uses, since it only
    # knows a taxonomy category's display name, never a pre-existing
    # Category id. Mirrors the CSV import path's category_cache pattern.
    category_name = serializer.validated_data.get('category_name', '').strip()
    if not category and category_name:
        category, _ = Category.objects.get_or_create(business=business, name=category_name)

    product = serializer.save(business=business, category=category)

    if product.cost_price is not None:
        from apps.reports.services import check_confidence_to_act_milestone
        check_confidence_to_act_milestone(business)

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

    # No is_active filter here (unlike product_list_create's listing
    # queryset) — a deactivated product must still be reachable by id so
    # PATCH { is_active: true } can bring it back. business scoping is
    # the real access boundary; is_active is a visibility/soft-delete
    # flag, not a security one.
    try:
        product = Product.objects.get(id=product_id, business=business)
    except Product.DoesNotExist:
        return Response(
            {'detail': MESSAGES['PRODUCT_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(ProductSerializer(product).data)

    # PATCH and DELETE both mutate the product — owner/manager only, same
    # tier as editing a product's sellable-form tree (see
    # product_unit_list_create above). Previously this endpoint had no
    # role check at all beyond being logged in, so any staff member
    # (including a cashier) could PATCH price, cost, category, or any
    # other field on any product.
    if not IsOwnerOrManager().has_permission(request, None):
        return Response({'detail': MESSAGES['OWNER_OR_MANAGER_ONLY']}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PATCH':
        serializer = ProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Block changing SKU directly
        serializer.validated_data.pop('sku', None)
        # Block changing current_stock through this general-purpose edit
        # endpoint too — current_stock only ever changes through
        # /transactions/stock-in/, /loss/, or a Count, each of which
        # writes a StockMovement row. Allowing it here as well would let
        # an edit silently change stock with no audit trail, breaking
        # the movement log every other stock change goes through.
        serializer.validated_data.pop('current_stock', None)

        # Validate an explicitly-given category id belongs to this
        # business — product_list_create's POST path already does this;
        # this PATCH path never did, so a bad/foreign category id would
        # silently link a product across tenants instead of 400ing.
        category = serializer.validated_data.get('category')
        if category and category.business_id != business.id:
            return Response(
                {'detail': MESSAGES['CATEGORY_WRONG_BUSINESS']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve category_name -> category, same get-or-create pattern
        # as product creation. ProductSerializer's category_name field is
        # read-only (it's a display field there — see the docstring on
        # ProductSerializer), so a category_name sent by the product-edit
        # screen's category picker never reaches validated_data on its
        # own; without this it would be silently ignored on every edit.
        # Only applies when no explicit category id was already sent.
        category_name = str(request.data.get('category_name', '') or '').strip()
        if not category and category_name:
            category, _ = Category.objects.get_or_create(business=business, name=category_name)
            serializer.validated_data['category'] = category

        cost_price_touched = 'cost_price' in serializer.validated_data
        serializer.save()
        if cost_price_touched:
            from apps.reports.services import check_confidence_to_act_milestone
            check_confidence_to_act_milestone(business)
        return Response(ProductSerializer(product).data)

    # DELETE — soft delete
    product.is_active = False
    product.save(update_fields=['is_active'])
    return Response({'detail': MESSAGES['PRODUCT_DELETED']}, status=status.HTTP_200_OK)


# ── Pack-to-unit selling (C10) ───────────────────────────────────────────────
# Manages a product's ProductUnit tree — the different sellable/stockable
# physical forms of one product (e.g. bag / gorogoro / sachet). Read is
# open to any authenticated staff (Sell mode needs it); write is
# owner/manager-only, same tier as editing the product itself.

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def product_unit_list_create(request, product_id):
    """
    GET  /api/v1/catalog/products/{id}/units/  — This product's unit tree.
    POST /api/v1/catalog/products/{id}/units/  — Add a new form.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        product = Product.objects.get(id=product_id, business=business, is_active=True)
    except Product.DoesNotExist:
        return Response({'detail': MESSAGES['PRODUCT_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        units = product.units.select_related('parent').order_by('created_at')
        return Response(ProductUnitSerializer(units, many=True).data)

    if not IsOwnerOrManager().has_permission(request, None):
        return Response({'detail': MESSAGES['OWNER_OR_MANAGER_ONLY']}, status=status.HTTP_403_FORBIDDEN)

    serializer = ProductUnitWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    parent = data.get('parent')
    if parent is not None and parent.product_id != product.id:
        return Response({'detail': MESSAGES['PRODUCT_UNIT_PARENT_WRONG_PRODUCT']}, status=status.HTTP_400_BAD_REQUEST)

    if data.get('is_root') and product.units.filter(is_root=True).exists():
        return Response({'detail': MESSAGES['PRODUCT_UNIT_ROOT_ALREADY_EXISTS']}, status=status.HTTP_400_BAD_REQUEST)

    # Pre-fill a true unit-of-measure ratio (litre:ml, kg:g, dozen:piece)
    # when the caller didn't supply one — see get_fixed_ratio(). Anything
    # container/packaging-based (gorogoro, pack, bag) has no default and
    # must come from the payload; validate() already rejected a missing
    # ratio for a non-root unit, so this only ever fills in a value that
    # would otherwise have failed.
    if parent is not None and data.get('ratio_to_parent') is None:
        fixed = get_fixed_ratio(parent.unit, data['unit'])
        if fixed is not None:
            data['ratio_to_parent'] = fixed
        else:
            return Response({'detail': MESSAGES['PRODUCT_UNIT_NEEDS_RATIO']}, status=status.HTTP_400_BAD_REQUEST)

    unit = ProductUnit(product=product, **data)
    try:
        unit.full_clean()
    except DjangoValidationError as e:
        return Response({'detail': '; '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
    unit.save()

    return Response(
        {'detail': MESSAGES['PRODUCT_UNIT_CREATED'], 'unit': ProductUnitSerializer(unit).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsNotExpired])
def product_unit_detail(request, product_id, unit_id):
    """
    GET    /api/v1/catalog/products/{id}/units/{unit_id}/
    PATCH  /api/v1/catalog/products/{id}/units/{unit_id}/
    DELETE /api/v1/catalog/products/{id}/units/{unit_id}/
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        unit = ProductUnit.objects.select_related('product', 'parent').get(
            id=unit_id, product_id=product_id, product__business=business,
        )
    except ProductUnit.DoesNotExist:
        return Response({'detail': MESSAGES['PRODUCT_UNIT_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(ProductUnitSerializer(unit).data)

    if not IsOwnerOrManager().has_permission(request, None):
        return Response({'detail': MESSAGES['OWNER_OR_MANAGER_ONLY']}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PATCH':
        serializer = ProductUnitWriteSerializer(unit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get('parent', unit.parent)
        if parent is not None and parent.product_id != unit.product_id:
            return Response({'detail': MESSAGES['PRODUCT_UNIT_PARENT_WRONG_PRODUCT']}, status=status.HTTP_400_BAD_REQUEST)

        for field, value in serializer.validated_data.items():
            setattr(unit, field, value)
        try:
            unit.full_clean()
        except DjangoValidationError as e:
            return Response({'detail': '; '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        unit.save()
        return Response({'detail': MESSAGES['PRODUCT_UNIT_UPDATED'], 'unit': ProductUnitSerializer(unit).data})

    # DELETE
    if unit.is_root:
        return Response({'detail': MESSAGES['PRODUCT_UNIT_CANNOT_DELETE_ROOT']}, status=status.HTTP_400_BAD_REQUEST)
    if unit.children.exists():
        return Response({'detail': MESSAGES['PRODUCT_UNIT_CANNOT_DELETE_HAS_CHILDREN']}, status=status.HTTP_400_BAD_REQUEST)
    unit.delete()
    return Response({'detail': MESSAGES['PRODUCT_UNIT_DELETED']}, status=status.HTTP_200_OK)


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

    if result['imported'] > 0:
        from apps.reports.services import check_confidence_to_act_milestone
        check_confidence_to_act_milestone(business)

    response_status = status.HTTP_200_OK if result['imported'] > 0 else status.HTTP_400_BAD_REQUEST
    return Response(result, status=response_status)