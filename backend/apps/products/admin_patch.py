"""
PATCH NOTES for apps/products/admin.py — apply by hand.

Add import:

    from .models_external_source import ExternalSource

Add to GlobalProductAdmin.list_display / readonly_fields nothing extra
is strictly needed (web_sources is an M2M, browsable via the existing
change form's automatic widget), but add it to list_filter alongside
status/source is NOT recommended — M2M filters get expensive fast on
this table; skip it.

Add a new registration:

    @admin.register(ExternalSource)
    class ExternalSourceAdmin(admin.ModelAdmin):
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
