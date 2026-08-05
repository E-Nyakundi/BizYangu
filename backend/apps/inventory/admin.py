"""
BizYangu — inventory admin.

Didn't exist before this build. Added alongside RepackageEvent (C10)
so both the existing StockMovement audit trail and the new
repackaging events are checkable in Django admin, same reasoning as
apps/catalog/admin.py: verify state without a raw DB query.
"""

from django.contrib import admin

from .models import StockMovement, RepackageEvent


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'product_unit', 'movement_type', 'quantity_change',
        'quantity_before', 'quantity_after', 'business', 'created_at',
    )
    list_filter = ('movement_type', 'business')
    search_fields = ('product__name', 'business__name', 'notes')
    readonly_fields = ('id',)
    ordering = ('-created_at',)


@admin.register(RepackageEvent)
class RepackageEventAdmin(admin.ModelAdmin):
    list_display = (
        'from_unit', 'to_unit', 'quantity_consumed', 'quantity_produced',
        'expected_yield', 'loss_quantity', 'performed_by', 'created_at',
    )
    list_filter = ('business',)
    search_fields = (
        'from_unit__product__name', 'to_unit__product__name',
        'business__name', 'notes',
    )
    readonly_fields = ('id', 'expected_yield', 'loss_quantity')
    ordering = ('-created_at',)
