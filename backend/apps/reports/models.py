"""
BizYangu — reports models.

Everything else in this app is computed on read (no Report model) — see
apps/reports/views.py. BusinessMilestone is the one deliberate exception:
milestones are *events* ("today was your best day ever"), not a live
snapshot, so they need a permanent row or the achievement is lost the
moment the underlying data moves on (tomorrow's sales don't erase that
yesterday was a record). Per the Phase 5 design note, this is checked
lazily from relevant call sites (sale creation, reconciliation resolve,
product cost-price writes) — no scheduled job.
"""

import uuid
from django.db import models


class BusinessMilestone(models.Model):
    class MilestoneType(models.TextChoices):
        HIGHEST_DAY_SALES = 'highest_day_sales', 'Highest single-day sales'
        FULLY_RECONCILED_WEEK = 'fully_reconciled_week', 'First fully-reconciled week'
        CONFIDENCE_TO_ACT = 'confidence_to_act', 'Cost-price coverage crossed 80%'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'business.Business', on_delete=models.CASCADE, related_name='milestones',
    )
    milestone_type = models.CharField(max_length=30, choices=MilestoneType.choices)
    # Generic numeric payload — the day's net revenue for HIGHEST_DAY_SALES,
    # the coverage percentage for CONFIDENCE_TO_ACT, unused (null) for
    # FULLY_RECONCILED_WEEK. Kept as one field rather than a type-specific
    # column each, since only one milestone type is ever read at a time.
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    achieved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-achieved_at']
        indexes = [
            models.Index(fields=['business', 'milestone_type', '-achieved_at']),
        ]

    def __str__(self):
        return f'{self.business_id} — {self.milestone_type} @ {self.achieved_at}'
