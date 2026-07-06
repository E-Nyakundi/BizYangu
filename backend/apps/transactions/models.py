"""
BizYangu — transactions models.
Transaction + TransactionItem. Signals update stock automatically.
"""

import re
import uuid
from django.db import models
from django.conf import settings


class Transaction(models.Model):
    class Type(models.TextChoices):
        SALE = 'SALE', 'Sale'
        STOCK_IN = 'STOCK_IN', 'Stock In'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        LOSS = 'LOSS', 'Loss'
        DAMAGE = 'DAMAGE', 'Damage'
        REFUND = 'REFUND', 'Refund'
        TRANSFER = 'TRANSFER', 'Transfer'

    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        MPESA = 'MPESA', 'M-Pesa'
        CREDIT = 'CREDIT', 'Credit'
        MIXED = 'MIXED', 'Mixed'

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        FAILED = 'FAILED', 'Failed'
        DISPUTED = 'DISPUTED', 'Disputed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.PROTECT, related_name='transactions')
    type = models.CharField(max_length=15, choices=Type.choices, default=Type.SALE)
    reference_number = models.CharField(max_length=20, unique=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.CONFIRMED)
    mpesa_reference = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    is_voided = models.BooleanField(default=False)
    void_reason = models.TextField(blank=True)
    void_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='voided_transactions',
    )
    # Set only on type=REFUND transactions — points back at the SALE being
    # refunded. Distinct from void: a void means the sale itself was a
    # mistake and never happened; a refund means the sale was real and the
    # customer returned goods/money afterward. The original sale stays
    # in reports; the refund is its own auditable transaction.
    original_transaction = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='refunds',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference_number} — {self.total_amount} KES'

    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Resolve business_id before hitting the DB.
            # self.business_id is set by Django when business= is passed to create(),
            # but resolve via .pk as belt-and-suspenders.
            business_id = self.business_id or (self.business.pk if self.business else None)
            self.reference_number = self._generate_reference(business_id)
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference(business_id) -> str:
        """
        Generate the next BY-YYYY-NNNN reference number for this business.

        Uses SELECT FOR UPDATE on the highest existing reference to prevent
        duplicate key races under concurrent requests.

        IMPORTANT: Do NOT wrap in db_transaction.atomic() here — this method
        is always called from within Transaction.save(), which is itself called
        from inside an atomic() block in the view. Nesting atomic() creates a
        savepoint, and SELECT FOR UPDATE inside a savepoint does not correctly
        block concurrent writers in PostgreSQL. The outer atomic() is sufficient.
        """
        from django.utils import timezone

        year = timezone.now().year
        prefix = f'BY-{year}-'

        # Lock the highest existing reference row for this business+year.
        # If no rows exist yet, the lock is a no-op and seq starts at 1.
        last = (
            Transaction.objects
            .select_for_update()
            .filter(
                business_id=business_id,
                reference_number__startswith=prefix,
            )
            .order_by('-reference_number')
            .values_list('reference_number', flat=True)
            .first()
        )

        if last:
            match = re.search(r'BY-\d{4}-(\d+)', last)
            seq = int(match.group(1)) + 1 if match else 1
        else:
            seq = 1

        return f'{prefix}{seq:04d}'


class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='transaction_items')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)  # Snapshot at time of sale
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # Snapshot
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    # Set only on items belonging to a REFUND transaction — points back at
    # the original SALE's line item being refunded. Used to compute how
    # much of that line has already been refunded, so partial refunds
    # (and repeated partial refunds) never exceed the quantity originally sold.
    original_item = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='refund_items',
    )

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product.name} × {self.quantity}'


# NOTE: Stock deduction for SALE transactions is handled explicitly inside
# apps/transactions/views.create_sale(), inside the same atomic() block that
# creates the TransactionItems. A post_save signal on Transaction was
# removed from here — it fired before items existed (instance.items.all()
# was always empty), so it never did anything. Restoring stock on void is
# likewise handled explicitly in views.void_transaction().
