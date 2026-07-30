"""
BizYangu — payments admin.

Added ahead of pilot launch. MPesaSTKRequest is the one you'll actually
want when a business calls saying "I paid but it's not showing" — status
here tells you whether Daraja ever called back at all, versus a bug on
our side.
"""

from django.contrib import admin

from .models import MPesaTransaction, MPesaSTKRequest


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
