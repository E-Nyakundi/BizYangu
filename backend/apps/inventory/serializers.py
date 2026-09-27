"""
BizYangu — inventory serializers.
StockMovement + stock level summaries.
"""

from decimal import Decimal

from rest_framework import serializers
from .models import StockMovement, RepackageEvent


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    # Only set for C10 movements (REPACKAGE_IN/OUT, or a sale/refund of a
    # specific sellable form) — null for every ordinary product-level
    # movement, same as the model field itself.
    product_unit_label = serializers.CharField(source='product_unit.get_unit_display', read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'product_unit', 'product_unit_label',
            'movement_type', 'quantity_change',
            'quantity_before', 'quantity_after',
            'notes', 'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = [
            'id', 'product_name', 'product_sku', 'product_unit_label', 'created_by_name', 'created_at',
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


# ── Pack-to-unit selling / repackaging (C10) ─────────────────────────────────

class RepackageEventSerializer(serializers.ModelSerializer):
    """Read shape — display-only, created via RepackageCreateSerializer below."""
    product_name = serializers.CharField(source='from_unit.product.name', read_only=True)
    from_unit_label = serializers.CharField(source='from_unit.get_unit_display', read_only=True)
    to_unit_label = serializers.CharField(source='to_unit.get_unit_display', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.name', read_only=True)

    class Meta:
        model = RepackageEvent
        fields = [
            'id', 'product_name',
            'from_unit', 'from_unit_label', 'to_unit', 'to_unit_label',
            'quantity_consumed', 'quantity_produced',
            'expected_yield', 'loss_quantity',
            'notes', 'performed_by', 'performed_by_name', 'created_at',
        ]
        read_only_fields = fields


class RepackageCreateSerializer(serializers.Serializer):
    """
    Used for POST /api/v1/inventory/repackage/
    Body: { from_unit_id, to_unit_id, quantity_consumed, quantity_produced, notes? }
    """
    from_unit_id = serializers.UUIDField()
    to_unit_id = serializers.UUIDField()
    quantity_consumed = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    quantity_produced = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
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
    # Sourced straight off the model's ImageField -- needs
    # context={'request': ...} at instantiation for DRF to build an
    # absolute URL (see the view below); with no request in context it
    # falls back to a relative path, which is still usable but less
    # convenient for a client that doesn't know the API host itself.
    image = serializers.ImageField(default=None)