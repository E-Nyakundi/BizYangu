"""
BizYangu — shared product identity views.

All routes under /api/v1/products/. Deliberately separate from
/api/v1/catalog/, which is where a business's own Product records live —
this app answers "what is this barcode" as knowledge shared across every
business, not "what does this business stock." See apps/products/models.py
for the full design note on why these are kept apart.
"""

from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired
from apps.core.messages import MESSAGES
from . import services
from .models import GlobalProduct
from .serializers import (
    CreateCandidateSerializer,
    GlobalProductSerializer,
    ResolveBarcodeRequestSerializer,
    VerifyGlobalProductSerializer,
)


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )
    return business, None


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def resolve_barcode(request):
    """
    POST /api/v1/products/resolve-barcode/
    { "barcode": "616110..." }

    Internal-lookup-only in this slice (no external web search yet — see
    module scope note in models.py). Returns one of:
      { state: "FOUND_INTERNAL", global_product: {...} }
      { state: "KNOWN_CANDIDATE", global_product: {...} }
      { state: "UNRESOLVED", global_product: null }
    Caller (web Sell/Stock scan flow) branches on `state`: FOUND_INTERNAL
    can auto-fill; KNOWN_CANDIDATE must ask "is this the product?" before
    filling anything in; UNRESOLVED falls through to manual entry.
    """
    serializer = ResolveBarcodeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    state, gp = services.resolve_barcode(serializer.validated_data['barcode'])
    return Response({
        'state': state,
        'global_product': GlobalProductSerializer(gp).data if gp else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def create_candidate(request):
    """
    POST /api/v1/products/candidates/
    { "barcode": ..., "name": ..., "brand": "", "category": "", "unit": "" }

    Called after resolve-barcode returned UNRESOLVED and the user typed
    in the product's details manually. That business becomes the
    candidate's first contributor (recorded as its own confirming
    GlobalProductVerification — see services.create_candidate), not an
    "owner" of the barcode. This only creates the shared-identity
    record; it does NOT create the business's own catalog.Product — the
    existing product-create flow (apps.catalog) still owns that, and
    should call this alongside it when a barcode was scanned and came
    back UNRESOLVED.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = CreateCandidateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        gp = services.create_candidate(
            barcode=data['barcode'],
            name=data['name'],
            brand=data.get('brand', ''),
            category=data.get('category', ''),
            unit=data.get('unit', ''),
            business=business,
        )
    except IntegrityError:
        return Response(
            {'detail': MESSAGES['GLOBAL_PRODUCT_ALREADY_EXISTS']},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(GlobalProductSerializer(gp).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def verify_global_product(request, barcode):
    """
    POST /api/v1/products/{barcode}/verify/
    { "matches_existing": true }
    or
    { "matches_existing": false, "name": "...", "brand": "...", ... }

    Called when a second (or later) business scans a barcode that
    resolve-barcode returned as KNOWN_CANDIDATE and the user answers the
    "is this the product?" prompt. One vote per business — scanning
    again later updates that business's existing vote rather than
    adding another one. See services.record_verification for the
    confirmation/conflict threshold logic.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        gp = GlobalProduct.objects.get(barcode=barcode)
    except GlobalProduct.DoesNotExist:
        return Response(
            {'detail': MESSAGES['GLOBAL_PRODUCT_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = VerifyGlobalProductSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    gp, _ = services.record_verification(
        gp, business,
        matches_existing=data['matches_existing'],
        proposed={
            'name': data.get('name', ''),
            'brand': data.get('brand', ''),
            'category': data.get('category', ''),
            'unit': data.get('unit', ''),
        },
    )
    return Response(GlobalProductSerializer(gp).data)
