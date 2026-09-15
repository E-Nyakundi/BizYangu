"""
BizYangu — background dispatch for web-search barcode discovery.

Execution model (design doc §4.6): resolve_barcode() keeps returning
UNRESOLVED immediately and synchronously — this task changes nothing
about that contract. It is fired *after* an UNRESOLVED response has
already gone back to the caller, from the view layer, purely to
populate GlobalProduct in the background so a *later* scan of the same
barcode (by this business or another) benefits. No "pending" state is
introduced anywhere in this pass — see §4.6's explicit note that the
scan which triggered the search gets no new UI treatment.
"""

import logging

from celery import shared_task

from . import webcrawl
from .models import GlobalProduct
from .models_external_source import ExternalSource

logger = logging.getLogger(__name__)


@shared_task(name='apps.products.tasks.discover_barcode_via_web')
def discover_barcode_via_web(barcode):
    """
    Runs the full search-and-crawl pipeline for one barcode and, if it
    produces a winning name, persists a CANDIDATE GlobalProduct with
    source=WEB_SEARCH — never VERIFIED (see webcrawl.py's module
    docstring for why that boundary is non-negotiable).

    Idempotent against races: if a GlobalProduct for this barcode
    already exists by the time this task runs (another business
    manually entered it, or a concurrent dispatch got there first),
    this is a no-op — get_or_create-style check up front, not an
    upsert, since a web-search guess should never overwrite whatever
    is already there, manual or otherwise.
    """
    barcode = (barcode or '').strip()
    if not barcode:
        return

    if GlobalProduct.objects.filter(barcode=barcode).exists():
        logger.info('discover_barcode_via_web: %s already has a GlobalProduct, skipping', barcode)
        return

    result = webcrawl.discover(barcode)
    if not result.candidate_name:
        logger.info(
            'discover_barcode_via_web: no candidate found for %s (considered=%d, fetched=%d)',
            barcode, result.raw_hits_considered, result.raw_hits_fetched,
        )
        return

    gp = _create_web_candidate(barcode, result.candidate_name, result.contributing_domains)
    logger.info(
        'discover_barcode_via_web: created CANDIDATE %s for %s from %d domain(s)',
        gp.pk, barcode, len(result.contributing_domains),
    )


def _create_web_candidate(barcode, name, contributing_domains):
    """
    Persists the CANDIDATE and records/updates each contributing
    ExternalSource row (creating it on first sight of a domain — see
    ExternalSource's docstring on when counters get updated later).

    Deliberately duplicates services.create_candidate's shape rather
    than calling it directly: that function always attaches a
    `business` as first contributor, which doesn't apply to a
    web-sourced candidate (no business typed anything in). Kept in
    this module rather than added as a branch inside
    services.create_candidate to avoid that function needing to know
    about web search at all — same separation-of-concerns reasoning as
    services.py's own module docstring about apps.catalog imports.
    """
    from django.db import transaction

    with transaction.atomic():
        gp = GlobalProduct.objects.create(
            barcode=barcode,
            name=name,
            status=GlobalProduct.Status.CANDIDATE,
            source=GlobalProduct.Source.WEB_SEARCH,
            confirmation_count=0,
        )
        for domain, kind in contributing_domains:
            source, _ = ExternalSource.objects.get_or_create(
                domain=domain,
                defaults={'kind': kind, 'candidates_contributed': 0},
            )
            source.candidates_contributed += 1
            source.save(update_fields=['candidates_contributed', 'updated_at'])
            gp.web_sources.add(source)
    return gp
