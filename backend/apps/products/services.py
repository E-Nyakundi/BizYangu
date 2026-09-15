"""
BizYangu — shared product identity: resolution + verification services.

Two entry points other apps/views should call:
  - resolve_barcode(barcode) -> (state, global_product)
  - record_verification(global_product, business, matches_existing, proposed=...)

Kept self-contained (only imports apps.business at call time inside the
FK, no imports from apps.catalog) so apps.catalog.views can import this
module without a circular-import problem — same reasoning as
apps.reports.services's module docstring.
"""

from django.db import transaction

from .models import GlobalProduct, GlobalProductVerification

# Five independent, non-conflicting confirmations required before a
# CANDIDATE is trusted enough to auto-fill future scans without asking.
# Deliberately not "five total votes" — a candidate sitting at 4
# confirmations + 3 conflicts never reaches this by accumulating more
# raw activity; see record_verification()'s DISPUTED branch below.
CONFIRMATIONS_REQUIRED = 5

# If conflicting evidence reaches this count, the candidate stops being
# a safe auto-suggestion even if it also has confirmations — surfaced
# for manual review rather than either side "winning" by volume.
CONFLICTS_TO_DISPUTE = 3


class ResolutionState:
    FOUND_INTERNAL = 'FOUND_INTERNAL'
    KNOWN_CANDIDATE = 'KNOWN_CANDIDATE'
    UNRESOLVED = 'UNRESOLVED'


def resolve_barcode(barcode):
    """
    Looks up a scanned barcode against the internal GlobalProduct table
    only — no external web search in this slice (see module scope note
    in models.py). Returns (state, global_product_or_None).

    FOUND_INTERNAL: a VERIFIED record exists — safe to auto-fill.
    KNOWN_CANDIDATE: a CANDIDATE (or DISPUTED) record exists — caller
      should show it to the user as "is this the product?" rather than
      auto-filling, per the design doc's confirm-don't-assume rule.
    UNRESOLVED: nothing known — caller falls through to today's manual
      entry flow.
    """
    barcode = (barcode or '').strip()
    if not barcode:
        return ResolutionState.UNRESOLVED, None

    gp = GlobalProduct.objects.filter(barcode=barcode).first()
    if gp is None:
        return ResolutionState.UNRESOLVED, None
    if gp.status == GlobalProduct.Status.VERIFIED:
        return ResolutionState.FOUND_INTERNAL, gp
    return ResolutionState.KNOWN_CANDIDATE, gp


@transaction.atomic
def create_candidate(barcode, name, brand='', category='', unit='', business=None):
    """
    Called the moment a business types in details for a barcode nothing
    else recognised — that business becomes the candidate's first
    contributor, recorded as its own GlobalProductVerification row
    (matches_existing=True against its own proposal) rather than as an
    "owner" field on GlobalProduct itself, per the design doc's explicit
    instruction not to model this as ownership.

    Returns the created GlobalProduct. Raises IntegrityError if the
    barcode already has a GlobalProduct — callers should resolve_barcode()
    first and only reach here on UNRESOLVED.
    """
    gp = GlobalProduct.objects.create(
        barcode=barcode.strip(),
        name=name,
        brand=brand,
        category=category,
        unit=unit,
        status=GlobalProduct.Status.CANDIDATE,
        source=GlobalProduct.Source.MANUAL,
        confirmation_count=1 if business else 0,
    )
    if business is not None:
        GlobalProductVerification.objects.create(
            global_product=gp,
            business=business,
            matches_existing=True,
            proposed_name=name,
            proposed_brand=brand,
            proposed_category=category,
            proposed_unit=unit,
        )
    return gp


@transaction.atomic
def record_verification(global_product, business, matches_existing, proposed=None):
    """
    Records one business's confirm/dispute vote on an existing
    GlobalProduct and re-evaluates its status.

    `proposed` (optional dict of name/brand/category/unit) is only
    meaningful when matches_existing=False — it's the conflicting
    evidence that business saw instead. Ignored otherwise.

    One row per (global_product, business) — a business re-scanning the
    same barcode updates its existing vote rather than adding a second
    one, so confirmation_count always reflects independent businesses.
    Uses select_for_update on the GlobalProduct row to keep concurrent
    votes from racing on the denormalized counters.
    """
    global_product = GlobalProduct.objects.select_for_update().get(pk=global_product.pk)
    proposed = proposed or {}

    verification, created = GlobalProductVerification.objects.update_or_create(
        global_product=global_product,
        business=business,
        defaults={
            'matches_existing': matches_existing,
            'proposed_name': proposed.get('name', ''),
            'proposed_brand': proposed.get('brand', ''),
            'proposed_category': proposed.get('category', ''),
            'proposed_unit': proposed.get('unit', ''),
        },
    )

    counts = global_product.verifications.aggregate(
        confirmations=_count_matching(True),
        conflicts=_count_matching(False),
    )
    global_product.confirmation_count = counts['confirmations']
    global_product.conflict_count = counts['conflicts']

    if global_product.conflict_count >= CONFLICTS_TO_DISPUTE:
        global_product.status = GlobalProduct.Status.DISPUTED
    elif global_product.confirmation_count >= CONFIRMATIONS_REQUIRED:
        global_product.status = GlobalProduct.Status.VERIFIED
    else:
        global_product.status = GlobalProduct.Status.CANDIDATE

    global_product.save(update_fields=['confirmation_count', 'conflict_count', 'status', 'updated_at'])
    return global_product, verification


def _count_matching(value):
    from django.db.models import Count, Q
    return Count('id', filter=Q(matches_existing=value))
