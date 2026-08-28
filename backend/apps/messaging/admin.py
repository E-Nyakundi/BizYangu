"""
BizYangu — messaging admin.

Read-only by design: this log exists to answer "which provider actually
delivered this OTP, and how often does each one fail" (see Phase 6.5,
BizYangu_Master_Plan.md §3.2/§6.5) — a raw admin edit of a delivery
record would defeat that purpose. No custom actions.
"""

from django.contrib import admin

from .models import SMSDeliveryLog


@admin.register(SMSDeliveryLog)
class SMSDeliveryLogAdmin(admin.ModelAdmin):
    list_display = (
        'phone_number', 'provider_name', 'success', 'purpose', 'created_at',
    )
    list_filter = ('provider_name', 'success', 'purpose')
    search_fields = ('phone_number', 'provider_message_id')
    readonly_fields = (
        'id', 'phone_number', 'provider_name', 'success',
        'provider_message_id', 'error', 'purpose', 'created_at',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
