"""
BizYangu — payments models.
M-Pesa transactions and STK Push requests.
"""

import uuid
from django.db import models


class MPesaTransaction(models.Model):
    class TransactionType(models.TextChoices):
        C2B = 'C2B', 'Customer to Business'
        STK_PUSH = 'STK_PUSH', 'STK Push'
        B2C = 'B2C', 'Business to Customer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.PROTECT, related_name='mpesa_transactions')
    transaction = models.ForeignKey(
        'transactions.Transaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mpesa_transactions',
    )
    mpesa_receipt_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = models.DateTimeField()
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    is_matched = models.BooleanField(default=False)
    is_reconciled = models.BooleanField(default=False)
    raw_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date']

    def __str__(self):
        return f'{self.mpesa_receipt_number} — {self.amount} KES'


class MPesaSTKRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        TIMEOUT = 'TIMEOUT', 'Timeout'

    business = models.ForeignKey('business.Business', on_delete=models.PROTECT, related_name='stk_requests')
    transaction = models.ForeignKey(
        'transactions.Transaction', on_delete=models.PROTECT, related_name='stk_requests',
    )
    checkout_request_id = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'STK {self.checkout_request_id} — {self.status}'
