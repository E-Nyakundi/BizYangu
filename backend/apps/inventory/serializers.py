"""
BizYangu — inventory serializers.
StockMovement + stock level summaries.
"""

from decimal import Decimal

from rest_framework import serializers
from .models import StockMovement


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'movement_type', 'quantity_change',
            'quantity_before', 'quantity_after',
            'notes', 'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = [
            'id', 'product_name', 'product_sku', 'created_by_name', 'created_at',
            'quantity_before', 'quantity_after',
        ]


class StockCountSerializer(serializers.Serializer):
    """
    Used for POST /api/v1/inventory/count/
    Submit a physical stock count for a product.
    """
    product_id = serializers.UUIDField()
    counted_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0'))
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class StockLevelSerializer(serializers.Serializer):
    """
    Summary of current stock for each product.
    Returned by GET /api/v1/inventory/
    """
    id = serializers.UUIDField()
    name = serializers.CharField()
    sku = serializers.CharField()
    current_stock = serializers.DecimalField(max_digits=12, decimal_places=3)
    low_stock_threshold = serializers.DecimalField(max_digits=12, decimal_places=3)
    stock_status = serializers.CharField()
    unit = serializers.CharField()
    category_name = serializers.CharField(source='category.name', default=None)
    track_stock = serializers.BooleanField()