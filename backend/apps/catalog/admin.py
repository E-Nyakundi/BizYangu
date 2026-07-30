"""
BizYangu — catalog admin.

Added ahead of pilot launch — lets you check a business's actual stock
state (e.g. "why does this product show 0 stock") without a DB query.
"""

from django.contrib import admin

from .models import Category, Product


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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'is_active')
    search_fields = ('name', 'business__name')
