"""
BizYangu — inventory models.
StockMovement audit trail.
"""

import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        SALE = 'SALE', 'Sale'
        RESTOCK = 'RESTOCK', 'Restock'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        LOSS = 'LOSS', 'Loss'
        DAMAGE = 'DAMAGE', 'Damage'
        REFUND = 'REFUND', 'Refund'
        COUNT = 'COUNT', 'Stock Count'
        # Pack-to-unit / repackaging (C10). Two rows per RepackageEvent
        # below — one negative against the source ProductUnit's pool,
        # one positive against the destination's — so the existing
        # audit trail and reports keep working for repackaging the same
        # way they already do for sales/restocks, with no separate
        # reporting path needed.
        REPACKAGE_OUT = 'REPACKAGE_OUT', 'Repackage (consumed)'
        REPACKAGE_IN = 'REPACKAGE_IN', 'Repackage (produced)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.PROTECT, related_name='stock_movements')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='stock_movements')
    # Null for products that don't use ProductUnit (the common case — a
    # single-form product just keeps using Product.current_stock as
    # before). Set when the movement is against a specific sellable
    # form of a multi-unit product (C10).
    product_unit = models.ForeignKey(
        'catalog.ProductUnit', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_movements',
    )
    transaction = models.ForeignKey(
        'transactions.Transaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_movements',
    )
    movement_type = models.CharField(max_length=15, choices=MovementType.choices)
    quantity_change = models.DecimalField(max_digits=12, decimal_places=3)  # Positive = in, Negative = out
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='stock_movements')
    created_at = models.DateTimeField(auto_now_add=True)
    # Phase 5 (offline sync) — set only for movements created via
    # apps.sync.views.push (currently: an offline stock count), never
    # for ones created through the live endpoint (those stay null).
    # Mirrors Transaction.sync_idempotency_key's exact purpose: lets a
    # device retry a push whose response it never received without
    # creating a second, duplicate movement. See that field's own
    # comment in apps/transactions/models.py for the full rationale.
    sync_idempotency_key = models.CharField(max_length=100, null=True, blank=True, unique=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        direction = '+' if self.quantity_change >= 0 else ''
        return f'{self.product.name}: {direction}{self.quantity_change} ({self.movement_type})'


class RepackageEvent(models.Model):
    """
    Records turning one physical form of a product into another —
    e.g. a 90kg bag of maize scooped into gorogoro tins, or a 20L
    debe of oil poured into mL bottles. Chains naturally: a
    RepackageEvent's `to_unit` can itself later be the `from_unit` of
    another event (bag -> tin -> sachet), since each is just another
    ProductUnit.

    Only valid for ProductUnit pairs where to_unit.is_repackaged=True
    and to_unit.parent == from_unit — enforced in clean(), not at the
    DB level, since it needs to inspect both related objects.

    quantity_produced is never assumed to equal the theoretical yield
    (quantity_consumed * to_unit.ratio_to_parent) — the gap is real
    loss (spillage, an underweight tin) and is captured automatically
    rather than requiring a separate manual "record loss" step.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.PROTECT, related_name='repackage_events')
    from_unit = models.ForeignKey(
        'catalog.ProductUnit', on_delete=models.PROTECT, related_name='repackage_events_consumed',
    )
    to_unit = models.ForeignKey(
        'catalog.ProductUnit', on_delete=models.PROTECT, related_name='repackage_events_produced',
    )
    quantity_consumed = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_produced = models.DecimalField(max_digits=12, decimal_places=3)
    # Stored rather than computed on read — to_unit.ratio_to_parent can
    # change later (owner corrects it after realizing gorogoros run
    # smaller than they thought), and this event's loss figure should
    # stay accurate to what the ratio actually was at the time, not
    # drift retroactively when the ratio is edited.
    expected_yield = models.DecimalField(max_digits=12, decimal_places=3)
    loss_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='repackage_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Phase 5 (offline sync) — set only for events created through
    # apps.sync.views.push (an offline repackage), never for ones
    # created through the live endpoint (those stay null). Mirrors
    # StockMovement.sync_idempotency_key's exact purpose: lets a device
    # retry a push whose response it never received without creating a
    # second, duplicate event. See that field's own comment for the
    # full rationale.
    sync_idempotency_key = models.CharField(max_length=100, null=True, blank=True, unique=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.from_unit} -> {self.to_unit}: {self.quantity_produced} produced ({self.created_at:%Y-%m-%d})'

    def clean(self):
        if self.to_unit_id and self.from_unit_id:
            if not self.to_unit.is_repackaged:
                raise ValidationError('to_unit must be a unit marked is_repackaged=True.')
            if self.to_unit.parent_id != self.from_unit_id:
                raise ValidationError('to_unit.parent must be from_unit — you can only repackage into a direct child form.')
            if self.from_unit.product_id != self.to_unit.product_id:
                raise ValidationError('from_unit and to_unit must belong to the same product.')
