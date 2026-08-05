"""
BizYangu — catalog admin.

Added ahead of pilot launch — lets you check a business's actual stock
state (e.g. "why does this product show 0 stock") without a DB query.
"""

from django.contrib import admin

from .models import Category, Product, ProductUnit


class ProductUnitInline(admin.TabularInline):
    model = ProductUnit
    fk_name = 'product'
    extra = 0
    fields = (
        'unit', 'parent', 'ratio_to_parent', 'is_repackaged',
        'stock_quantity', 'selling_price', 'is_sellable', 'is_root',
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'business', 'category', 'selling_price', 'current_stock',
        'low_stock_threshold', 'track_stock', 'is_active',
    )
    list_filter = ('unit', 'track_stock', 'is_active')
    search_fields = ('name', 'sku', 'barcode', 'business__name')
    readonly_fields = ('id',)
    ordering = ('business', 'name')
    inlines = [ProductUnitInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'is_active')
    search_fields = ('name', 'business__name')


@admin.register(ProductUnit)
class ProductUnitAdmin(admin.ModelAdmin):
    # Standalone view kept alongside the Product inline above — the
    # inline is handy for checking one product's whole tree at a
    # glance; this is handy for e.g. finding every is_repackaged unit
    # across all businesses when debugging.
    list_display = (
        'product', 'unit', 'parent', 'ratio_to_parent', 'is_repackaged',
        'stock_quantity', 'selling_price', 'is_sellable', 'is_root',
    )
    list_filter = ('unit', 'is_repackaged', 'is_root', 'is_sellable')
    search_fields = ('product__name', 'product__business__name')
    readonly_fields = ('id',)
