"""
BizYangu — shared product identity admin.

Lets you inspect a barcode's evidence trail directly — which businesses
confirmed or disputed it, and why a candidate hasn't reached VERIFIED.
"""

from django.contrib import admin

from .models import ExternalSource, GlobalProduct, GlobalProductVerification


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


@admin.register(ExternalSource)
class ExternalSourceAdmin(admin.ModelAdmin):
    # web_sources is browsable via GlobalProduct's own change form
    # (automatic M2M widget) — not added to list_filter here, per
    # models_patch.py's note: M2M filters get expensive fast on this
    # table.
    list_display = (
        'domain', 'kind', 'candidates_contributed',
        'hits_confirmed', 'hits_disputed', 'reliability_ratio', 'updated_at',
    )
    list_filter = ('kind',)
    search_fields = ('domain',)
    readonly_fields = ('id', 'candidates_contributed', 'hits_confirmed', 'hits_disputed')

    def reliability_ratio(self, obj):
        ratio = obj.reliability_ratio
        return '—' if ratio is None else f'{ratio:.0%}'
    reliability_ratio.short_description = 'Reliability'
