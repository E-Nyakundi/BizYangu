"""
BizYangu — knowledge base views (Phase 8 taxonomy, wired in Phase 9).
Read-only: this data is version-controlled JSON, never written to via
the API. Authenticated (not public) purely for consistency with the
rest of the API — none of it is business-sensitive.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import Product
from apps.core.messages import MESSAGES
from . import loader


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )
    return business, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def business_type_list(request):
    """GET /api/v1/knowledge/business-types/ — the Phase 8 first-cohort list."""
    return Response(loader.list_business_types())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def taxonomy_detail(request, business_type_id):
    """
    GET /api/v1/knowledge/taxonomy/{business_type_id}/
    Resolved category -> subcategory -> item -> brand/unit tree for one
    business type, for the onboarding category picker and the
    reconciliation queue's "pick from taxonomy" flow.
    """
    taxonomy = loader.get_taxonomy(business_type_id)
    if taxonomy is None:
        return Response(
            {'detail': f'No taxonomy template exists yet for "{business_type_id}".'},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(taxonomy)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def category_suggestions(request, category_id):
    """
    GET /api/v1/knowledge/suggestions/{category_id}/
    Within-business suggestion fast track (Build Plan v3 §2.3, Phase 9
    item 6): once this business has 2+ products tagged with this taxonomy
    category, surface the category's other common brands/names as
    tap-to-accept suggestions. `unlocked: false` before that threshold —
    frontend shows nothing (or a plainer "type a name" field) until then.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    category_meta = loader.get_category_meta(category_id)
    if category_meta is None:
        return Response({'detail': 'Unknown category_id.'}, status=status.HTTP_404_NOT_FOUND)

    existing_products = Product.objects.filter(
        business=business, taxonomy_category_id=category_id, is_active=True,
    )
    count = existing_products.count()
    existing_names = {p.name.strip().lower() for p in existing_products}
    existing_brands = {p.taxonomy_brand.strip().lower() for p in existing_products if p.taxonomy_brand}

    unlocked = count >= 2
    names, brands = ([], []) if not unlocked else loader.find_category_brands_and_names(category_id)

    return Response({
        'category_id': category_id,
        'category_name': category_meta.get('name', category_id),
        'business_item_count': count,
        'unlocked': unlocked,
        'suggested_names': [n for n in names if n.strip().lower() not in existing_names],
        'suggested_brands': [b for b in brands if b.strip().lower() not in existing_brands],
    })
