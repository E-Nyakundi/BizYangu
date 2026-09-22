"""
BizYangu — payments models.
M-Pesa transactions and STK Push requests.
"""

import uuid
from django.db import models

from .fields import EncryptedCharField


class BusinessMpesaCredentials(models.Model):
    """
    A business's own Daraja app — their own till/paybill, so their
    customers' STK Push payments land directly in the business's own
    M-Pesa account instead of the shared sales shortcode. Optional:
    a business with no row here (or is_active=False) just falls back
    to the shared shortcode — see daraja.resolve_sales_credentials().

    consumer_secret/passkey are encrypted at rest (see fields.py).
    shortcode/consumer_key are not secret — a till/paybill number is
    public by definition (customers dial it), and a consumer key
    alone is useless without the secret.
    """
    class TillType(models.TextChoices):
        PAYBILL = 'PAYBILL', 'Paybill'
        BUY_GOODS = 'BUY_GOODS', 'Buy Goods (Till)'

    class Env(models.TextChoices):
        SANDBOX = 'sandbox', 'Sandbox'
        PRODUCTION = 'production', 'Production'

    business = models.OneToOneField(
        'business.Business', on_delete=models.CASCADE, related_name='mpesa_credentials',
    )
    till_type = models.CharField(max_length=10, choices=TillType.choices, default=TillType.PAYBILL)
    shortcode = models.CharField(max_length=20, blank=True)
    consumer_key = models.CharField(max_length=200, blank=True)
    consumer_secret = EncryptedCharField(max_length=500, blank=True)
    passkey = EncryptedCharField(max_length=500, blank=True)
    env = models.CharField(max_length=10, choices=Env.choices, default=Env.SANDBOX)

    # Off by default: an owner filling in the form shouldn't start
    # routing real customer payments until they've confirmed the
    # credentials actually work (see the /verify/ endpoint).
    is_active = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'business M-Pesa credentials'
        verbose_name_plural = 'business M-Pesa credentials'

    def __str__(self):
        return f'{self.business.name} — {self.get_till_type_display()} {self.shortcode or "(not set)"}'

    def is_configured(self) -> bool:
        return bool(self.consumer_key and self.consumer_secret and self.shortcode and self.passkey)


class MPesaTransaction(models.Model):
    class TransactionType(models.TextChoices):
        C2B = 'C2B', 'Customer to Business'
        STK_PUSH = 'STK_PUSH', 'STK Push'
        B2C = 'B2C', 'Business to Customer'
        SMS = 'SMS', 'SMS Reconciliation'

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


class SubscriptionPayment(models.Model):
    """
    A payment of a business's BizYangu subscription fee — money going
    TO the company (BizYangu), not a sale a business made. Uses the
    company shortcode (daraja.company_credentials()), completely
    separate from MPesaSTKRequest/MPesaTransaction above, which are
    always about a business's own sales.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        TIMEOUT = 'TIMEOUT', 'Timeout'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'business.Business', on_delete=models.PROTECT, related_name='subscription_payments',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    months = models.PositiveIntegerField(default=1)  # how many months this payment covers
    checkout_request_id = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.TextField(blank=True)
    raw_callback_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Subscription {self.checkout_request_id} — {self.business.name} — {self.status}'


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
