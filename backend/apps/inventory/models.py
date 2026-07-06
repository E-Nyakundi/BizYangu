"""
BizYangu — inventory models.
StockMovement audit trail.
"""

import uuid
from django.db import models
from django.conf import settings


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        SALE = 'SALE', 'Sale'
        RESTOCK = 'RESTOCK', 'Restock'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        LOSS = 'LOSS', 'Loss'
        DAMAGE = 'DAMAGE', 'Damage'
        REFUND = 'REFUND', 'Refund'
        COUNT = 'COUNT', 'Stock Count'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.PROTECT, related_name='stock_movements')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='stock_movements')
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

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        direction = '+' if self.quantity_change >= 0 else ''
        return f'{self.product.name}: {direction}{self.quantity_change} ({self.movement_type})'
