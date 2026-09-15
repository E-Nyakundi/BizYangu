"""
PATCH NOTES for apps/products/views.py — apply by hand.

In resolve_barcode(), after the existing services.resolve_barcode()
call, dispatch the background task on UNRESOLVED only:

    from . import services
    from .tasks import discover_barcode_via_web

    ...

    state, gp = services.resolve_barcode(serializer.validated_data['barcode'])
    if state == services.ResolutionState.UNRESOLVED:
        discover_barcode_via_web.delay(serializer.validated_data['barcode'])
    return Response({
        'state': state,
        'global_product': GlobalProductSerializer(gp).data if gp else None,
    })

No other change to this view — response shape, status code, and the
FOUND_INTERNAL/KNOWN_CANDIDATE branches are all untouched, per design
doc §4.6 / §5's "no change to resolve_barcode()'s response shape or
synchronous contract."

---

PATCH NOTES for bizyangu/settings/base.py — add near the existing
GOOGLE_OAUTH_CLIENT_IDS / MPESA_* block, same config()-from-env style:

    # Google Programmable Search Engine (Custom Search JSON API) — web-
    # search-assisted barcode discovery, see
    # apps/products/webcrawl.py and barcode-webcrawl-resolution-scoping.md.
    # Blank means webcrawl._search_google() logs a warning and returns
    # [], which discover() treats the same as "no results" — i.e. an
    # unconfigured environment degrades to UNRESOLVED-only behavior
    # exactly like before this phase existed, same pattern as
    # MOBIWAVE_API_KEY's blank-default fallback above.
    GOOGLE_CSE_API_KEY = config('GOOGLE_CSE_API_KEY', default='')
    GOOGLE_CSE_ENGINE_ID = config('GOOGLE_CSE_ENGINE_ID', default='')

Add both keys (blank) to .env.production.example / env.production.example
alongside the existing placeholder pattern — NOT with real values, per
the already-fixed secret-scrubbing incident logged for this project.
