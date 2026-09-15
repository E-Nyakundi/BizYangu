"""
BizYangu — shared product identity admin.

Lets you inspect a barcode's evidence trail directly — which businesses
confirmed or disputed it, and why a candidate hasn't reached VERIFIED.
"""

from django.contrib import admin

from .models import GlobalProduct, GlobalProductVerification


class GlobalProductVerificationInline(admin.TabularInline):
    model = GlobalProductVerification
    extra = 0
    fields = ('business', 'matches_existing', 'proposed_name', 'proposed_brand', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(GlobalProduct)
class GlobalProductAdmin(admin.ModelAdmin):
    list_display = (
        'barcode', 'name', 'brand', 'status', 'source',
        'confirmation_count', 'conflict_count', 'updated_at',
    )
    list_filter = ('status', 'source')
    search_fields = ('barcode', 'name', 'brand')
    readonly_fields = ('id', 'confirmation_count', 'conflict_count')
    inlines = [GlobalProductVerificationInline]


@admin.register(GlobalProductVerification)
class GlobalProductVerificationAdmin(admin.ModelAdmin):
    list_display = ('global_product', 'business', 'matches_existing', 'created_at')
    list_filter = ('matches_existing',)
    search_fields = ('global_product__barcode', 'business__name')
    readonly_fields = ('id',)
