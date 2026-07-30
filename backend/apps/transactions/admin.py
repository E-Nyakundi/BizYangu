"""
BizYangu — transactions admin.

Added ahead of pilot launch so "did this sale go through" is answerable
from admin directly, instead of a DB query. Read-only in spirit — no
custom actions that mutate a transaction from here; voiding/refunding
stays in the app's own reviewed flow (see apps.transactions.views),
not a raw admin edit.
"""

from django.contrib import admin

from .models import Transaction, TransactionItem


class TransactionItemInline(admin.TabularInline):
    model = TransactionItem
    extra = 0
    readonly_fields = ('product', 'name', 'quantity', 'unit_price', 'is_reconciled')
    can_delete = False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number', 'business', 'type', 'total_amount',
        'payment_method', 'payment_status', 'is_voided', 'created_at',
    )
    list_filter = ('type', 'payment_method', 'payment_status', 'is_voided')
    search_fields = (
        'reference_number', 'mpesa_reference', 'business__name',
        'created_by__phone_number',
    )
    readonly_fields = (
        'id', 'created_at', 'created_by', 'business', 'total_amount',
    )
    ordering = ('-created_at',)
    inlines = [TransactionItemInline]
