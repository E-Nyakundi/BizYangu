"""
BizYangu — business admin.

No admin.py existed anywhere in the project before this — Django admin
was wired into bizyangu/urls.py from the start but nothing was ever
registered with it. This is Phase 6's "dormancy admin view/saved filter"
requirement: since there's no WhatsApp Business API integration to push
automated nudges, "flag dormant businesses" means a Django admin view
Edgar checks manually alongside the pilot WhatsApp group — not a
scheduled job or a notification pipeline that doesn't exist.
"""

from django.contrib import admin
from django.db.models import Max
from django.utils import timezone

from .models import Business


class DormancyFilter(admin.SimpleListFilter):
    """Filters the business list by how long it's been since their last
    real sale — annotated on the queryset in BusinessAdmin.get_queryset,
    not recomputed here, so this filter and the last_sale_at column
    always agree with each other."""

    title = 'sales activity'
    parameter_name = 'dormancy'

    def lookups(self, request, model_admin):
        return (
            ('active_7', 'Active in last 7 days'),
            ('dormant_7', 'Dormant 7+ days'),
            ('dormant_14', 'Dormant 14+ days'),
            ('never_sold', 'Never made a sale'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset

        now = timezone.now()
        if value == 'active_7':
            return queryset.filter(_last_sale__gte=now - timezone.timedelta(days=7))
        if value == 'dormant_7':
            return queryset.filter(_last_sale__lt=now - timezone.timedelta(days=7)) \
                | queryset.filter(_last_sale__isnull=True)
        if value == 'dormant_14':
            return queryset.filter(_last_sale__lt=now - timezone.timedelta(days=14)) \
                | queryset.filter(_last_sale__isnull=True)
        if value == 'never_sold':
            return queryset.filter(_last_sale__isnull=True)
        return queryset


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'type', 'subscription_status', 'last_sale_at',
        'created_at', 'is_active',
    )
    list_filter = ('subscription_status', 'type', 'is_active', DormancyFilter)
    search_fields = ('name', 'owner__phone_number', 'owner__name')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # One aggregate per page load, not per row — annotate here so
        # both the column and the filter above read the same value.
        return qs.annotate(_last_sale=Max('transactions__created_at'))

    def last_sale_at(self, obj):
        return obj._last_sale
    last_sale_at.short_description = 'Last sale'
    last_sale_at.admin_order_field = '_last_sale'
