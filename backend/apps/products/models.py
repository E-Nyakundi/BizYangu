"""
BizYangu — shared product identity models.

This app answers "what is this barcode" as knowledge shared across every
BizYangu business. It is deliberately separate from apps.catalog.Product,
which answers "what does *this* business sell it for, and how much do
they have" — see the design note in resolve-barcode's view docstring for
why those two questions must never be merged into one model.

Scope for this pass (smallest safe slice, per the barcode-resolution
design doc): internal candidate/consensus loop only. No external web
search / Google discovery layer yet — GlobalProduct.source has a
WEB_SEARCH choice reserved for that follow-up phase, but nothing in this
app populates it today. No ExternalSource/reliability-tracking model
either, for the same reason — build it once the internal loop is proven.
"""

import uuid

from django.db import models


class GlobalProduct(models.Model):
    """
    A barcode's shared identity, independent of any one business.

    Starts life as a CANDIDATE the moment some business first types in
    details for a barcode nothing else recognises (that business is its
    *contributor*, not its owner — see GlobalProductVerification for how
    other businesses add evidence). Moves to VERIFIED once enough
    independent, non-conflicting confirmations accumulate — see
    CONFIRMATIONS_REQUIRED and services.record_verification().

    Deliberately no `owner`/`business` FK here — a GlobalProduct is
    common knowledge, not one business's record. Which businesses have
    weighed in lives on GlobalProductVerification instead.
    """

    class Status(models.TextChoices):
        CANDIDATE = 'CANDIDATE', 'Candidate'
        VERIFIED = 'VERIFIED', 'Verified'
        # A candidate with enough conflicting (non-matching) votes to be
        # untrustworthy as an auto-fill suggestion, without discarding
        # the barcode or its evidence trail. Never set automatically by
        # a simple majority — see services.record_verification().
        DISPUTED = 'DISPUTED', 'Disputed'

    class Source(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual entry'
        # Reserved for the not-yet-built web-search discovery phase.
        WEB_SEARCH = 'WEB_SEARCH', 'Web search'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    barcode = models.CharField(max_length=100, unique=True, db_index=True)

    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=20, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CANDIDATE)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)

    # Denormalized counters kept in sync by services.record_verification()
    # inside a single atomic transaction — cheap reads for the resolve
    # endpoint and admin list view. GlobalProductVerification rows remain
    # the source of truth; these are a cache, not the ledger.
    confirmation_count = models.PositiveIntegerField(default=0)
    conflict_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.barcode} — {self.name}'


class GlobalProductVerification(models.Model):
    """
    One business's evidence for or against a GlobalProduct's current
    identity — the audit trail behind confirmation_count/conflict_count.

    A business gets exactly one row per GlobalProduct (unique_together
    below): scanning the same barcode again later updates evidence
    rather than casting a second vote, so the count reflects independent
    businesses, not independent scans.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    global_product = models.ForeignKey(
        GlobalProduct, on_delete=models.CASCADE, related_name='verifications',
    )
    business = models.ForeignKey(
        'business.Business', on_delete=models.CASCADE, related_name='product_verifications',
    )

    # True: this business scanned the barcode and confirmed the
    # GlobalProduct's current name/brand/category/unit matched what
    # they were holding. False: they said it didn't match — the
    # proposed_* fields below capture what they saw instead, as
    # conflicting evidence (never silently overwriting the record).
    matches_existing = models.BooleanField()
    proposed_name = models.CharField(max_length=200, blank=True)
    proposed_brand = models.CharField(max_length=100, blank=True)
    proposed_category = models.CharField(max_length=100, blank=True)
    proposed_unit = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('global_product', 'business')]

    def __str__(self):
        verdict = 'confirms' if self.matches_existing else 'disputes'
        return f'{self.business} {verdict} {self.global_product.barcode}'
