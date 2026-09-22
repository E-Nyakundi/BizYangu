"""
BizYangu — messaging models (Phase 6.5).

SMSDeliveryLog is what actually lets BizYangu compare AT vs MobiWave (or
any future provider) on real delivery data instead of trusting a pricing
page — see BizYangu_Master_Plan.md §3.2 for why that matters. One row per
send *attempt* against a single provider, not one row per OTP: if AT
fails and MobiWave succeeds as a fallback, that's two rows, so failover
behavior itself is visible in the data, not just the final outcome.
"""

import uuid

from django.db import models


class SMSDeliveryLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Nullable + no FK: a delivery attempt can happen before we know which
    # business a phone number belongs to (e.g. OTP during signup, before
    # any Business row exists for this user yet). Storing the raw phone
    # number is enough for pilot-scale debugging; do not join this to
    # PII-heavy tables without a reason.
    phone_number = models.CharField(max_length=20)
    provider_name = models.CharField(max_length=50)
    success = models.BooleanField()
    provider_message_id = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    # Which logical send this was — lets OTP failures be queried
    # separately from future broadcast/receipt sends without needing a
    # second table yet. Free-text on purpose: this is Phase 6.5's SMS
    # channel only (see Explicitly deferred in the plan) — a WhatsApp/
    # email channel later would likely want its own log table rather than
    # overloading this one, not a new value here.
    purpose = models.CharField(max_length=50, default='otp')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        # Explicit names, matching migration 0001_initial's
        # auto-generated ones exactly — Django's makemigrations --check
        # compares index state by name, and an unnamed Index() here
        # gets re-derived from current model state rather than reading
        # back what the migration actually recorded, which is what was
        # producing this app's spurious "changes not yet reflected in
        # a migration" drift warning (fields matched exactly; only the
        # index names were being silently re-inferred and disagreeing).
        indexes = [
            models.Index(fields=['provider_name', 'created_at'], name='messaging_s_provide_9c1a4e_idx'),
            models.Index(fields=['phone_number', 'created_at'], name='messaging_s_phone_n_6f2b3d_idx'),
        ]

    def __str__(self):
        status = 'OK' if self.success else 'FAILED'
        return f'{self.provider_name} -> {self.phone_number} [{status}]'
