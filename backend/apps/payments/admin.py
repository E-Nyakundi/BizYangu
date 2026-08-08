"""
BizYangu — payments admin.

Added ahead of pilot launch. MPesaSTKRequest is the one you'll actually
want when a business calls saying "I paid but it's not showing" — status
here tells you whether Daraja ever called back at all, versus a bug on
our side.
"""

from django.contrib import admin

from .models import MPesaTransaction, MPesaSTKRequest, SubscriptionPayment, BusinessMpesaCredentials


@admin.register(MPesaSTKRequest)
class MPesaSTKRequestAdmin(admin.ModelAdmin):
    list_display = (
        'checkout_request_id', 'business', 'phone_number', 'amount',
        'status', 'result_code', 'created_at', 'completed_at',
    )
    list_filter = ('status',)
    search_fields = (
        'checkout_request_id', 'merchant_request_id', 'phone_number',
        'business__name',
    )
    readonly_fields = [f.name for f in MPesaSTKRequest._meta.fields]
    ordering = ('-created_at',)


@admin.register(MPesaTransaction)
class MPesaTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'mpesa_receipt_number', 'business', 'phone_number', 'amount',
        'transaction_type', 'is_matched', 'is_reconciled', 'created_at',
    )
    list_filter = ('transaction_type', 'is_matched', 'is_reconciled')
    search_fields = ('mpesa_receipt_number', 'phone_number', 'business__name')
    readonly_fields = [f.name for f in MPesaTransaction._meta.fields]
    ordering = ('-created_at',)


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'business', 'amount', 'months', 'status', 'phone_number',
        'mpesa_receipt_number', 'created_at', 'completed_at',
    )
    list_filter = ('status',)
    search_fields = (
        'checkout_request_id', 'merchant_request_id', 'phone_number',
        'mpesa_receipt_number', 'business__name',
    )
    readonly_fields = [f.name for f in SubscriptionPayment._meta.fields]
    ordering = ('-created_at',)


@admin.register(BusinessMpesaCredentials)
class BusinessMpesaCredentialsAdmin(admin.ModelAdmin):
    # consumer_secret/passkey deliberately excluded from list_display
    # AND from the change form's readonly display of raw values —
    # Django will still show them as editable password-like text
    # inputs (needed so support can help a business fix a typo), but
    # they never appear in the list view.
    list_display = (
        'business', 'till_type', 'shortcode', 'env', 'is_active', 'verified_at', 'updated_at',
    )
    list_filter = ('till_type', 'env', 'is_active')
    search_fields = ('business__name', 'shortcode', 'consumer_key')
    readonly_fields = ('created_at', 'updated_at', 'verified_at')
    ordering = ('-updated_at',)
