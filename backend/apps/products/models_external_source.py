"""
BizYangu — external-source reliability tracking (web-search discovery
layer, phase 2). See barcode-webcrawl-resolution-scoping.md §4.7.

This is intentionally its own module rather than added inline to
models.py: the design doc explicitly left the schema open pending real
extraction field shapes, and keeping it separable makes that easy to
revise without touching the already-stable GlobalProduct/
GlobalProductVerification pair. Import both from apps.products.models
as usual — see the `from .models_external_source import *`-style
re-export at the bottom of models.py once wired in.

Per-domain, not per-pattern, for this pass: barcode-list.com and any
future aggregator each get their own row, so "aggregator-shaped
snippet" scoring (webcrawl.py) and "this domain's actual track record"
tracking (this model) stay separate concerns. A per-pattern scheme
(e.g. one row for "all aggregator-shaped sites") was considered and
rejected for now — it would hide a newly-onboarded bad domain behind
an aggregate that's mostly good, which defeats the point of tracking
reliability per source at all. Revisit if/when a second aggregator
domain actually shows up in production data.
"""

import uuid

from django.db import models


class ExternalSource(models.Model):
    """
    Tracks, per source domain, how often its web-search hits have gone
    on to be confirmed vs. disputed by the existing internal voting
    loop (GlobalProductVerification) — the same reliability concept
    apps.payments and apps.reports already apply to their own domains.

    A row is created the first time a domain produces a CANDIDATE via
    create_web_candidate() (see webcrawl.py), and its counters are
    updated later — not at candidate-creation time, since reliability
    is about outcomes, not raw hit volume. Wiring that update into
    services.record_verification()'s existing atomic block is left for
    when GlobalProduct gains a way to trace a CANDIDATE back to the
    ExternalSource(s) that produced it (see GlobalProduct.web_sources
    in models.py's webcrawl extension) — no decay/window semantics are
    implemented yet; hits_confirmed/hits_disputed are simple lifetime
    counters for this pass, per the doc's "left for implementation
    time" note.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # e.g. "barcode-list.com", "cleanshelf.online" — bare registrable
    # domain, not a full URL, so multiple pages/paths on the same site
    # roll up into one reliability score.
    domain = models.CharField(max_length=255, unique=True, db_index=True)

    # Set at candidate-creation time based on which extractor matched
    # (see webcrawl.py's AGGREGATOR / RETAILER kinds) — informational
    # only; reliability is judged on hits_confirmed/hits_disputed, not
    # on this label, since a retailer-shaped domain could still turn
    # out unreliable in practice and the doc is explicit that trust
    # should be earned by outcome.
    class Kind(models.TextChoices):
        AGGREGATOR = 'AGGREGATOR', 'Aggregator (barcode-list.com-style)'
        RETAILER = 'RETAILER', "Retailer's own product page"
        OTHER = 'OTHER', 'Other'

    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.OTHER)

    # Lifetime counts of how many CANDIDATEs this domain contributed to
    # that later resolved VERIFIED vs. DISPUTED via the internal loop.
    # A CANDIDATE still sitting at CANDIDATE status contributes to
    # neither count yet.
    hits_confirmed = models.PositiveIntegerField(default=0)
    hits_disputed = models.PositiveIntegerField(default=0)

    # Total CANDIDATEs this domain has ever contributed to, regardless
    # of outcome — the denominator hits_confirmed/hits_disputed are
    # judged against, and also a quick "has this domain even been seen
    # enough times to trust its ratio" signal on its own.
    candidates_contributed = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-hits_confirmed']

    def __str__(self):
        return f'{self.domain} ({self.hits_confirmed}c/{self.hits_disputed}d)'

    @property
    def reliability_ratio(self):
        """
        Simple confirmed / (confirmed + disputed) ratio, or None if
        this domain has no resolved outcomes yet (still-CANDIDATE hits
        don't count either way). None rather than 0 or 1 so callers
        can distinguish "no data yet" from "0% reliable" — a domain
        with zero resolved outcomes is unproven, not untrustworthy.
        """
        resolved = self.hits_confirmed + self.hits_disputed
        if resolved == 0:
            return None
        return self.hits_confirmed / resolved
