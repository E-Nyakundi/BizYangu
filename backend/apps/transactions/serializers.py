"""
BizYangu — transactions serializers.
Sale creation, transaction listing, void.
"""

from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum
from .models import Transaction, TransactionItem
from apps.catalog.models import Product

User = get_user_model()


class TransactionItemCreateSerializer(serializers.Serializer):
    """Single line item in a sale. Nested inside SaleCreateSerializer."""
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))


class SaleCreateSerializer(serializers.Serializer):
    """
    POST /api/v1/transactions/sale/
    Creates a Transaction of type SALE + its TransactionItems.
    """
    items = TransactionItemCreateSerializer(many=True, min_length=1)
    payment_method = serializers.ChoiceField(
        choices=Transaction.PaymentMethod.choices,
        default=Transaction.PaymentMethod.CASH,
    )
    mpesa_reference = serializers.CharField(max_length=50, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate_mpesa_reference(self, value):
        return value.strip().upper() if value else ''


class StockInSerializer(serializers.Serializer):
    """POST /api/v1/transactions/stock-in/ — Add stock delivery."""
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class AdjustmentSerializer(serializers.Serializer):
    """POST /api/v1/transactions/adjustment/ or /loss/ — Manual adjustment."""
    product_id = serializers.UUIDField()
    quantity_change = serializers.DecimalField(max_digits=12, decimal_places=3)
    reason = serializers.ChoiceField(
        choices=['ADJUSTMENT', 'LOSS', 'DAMAGE'],
        default='ADJUSTMENT',
    )
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class TransactionItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)

    class Meta:
        model = TransactionItem
        fields = ['id', 'product', 'product_name', 'product_sku',
                  'quantity', 'unit_price', 'cost_price', 'subtotal', 'original_item']
        read_only_fields = ['id', 'product_name', 'product_sku', 'subtotal', 'original_item']


class TransactionSerializer(serializers.ModelSerializer):
    items = TransactionItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    refunded_amount = serializers.SerializerMethodField()

    def get_refunded_amount(self, obj):
        # Only meaningful on SALE transactions — sum of all non-voided
        # refunds issued against this sale. Frontend uses this to show
        # "KES X refunded" on the transaction detail / history views.
        if obj.type != Transaction.Type.SALE:
            return None
        total = obj.refunds.filter(is_voided=False).aggregate(
            total=Sum('total_amount')
        )['total']
        return str(total) if total else '0.00'

    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'reference_number', 'total_amount',
            'payment_method', 'payment_status', 'mpesa_reference',
            'notes', 'created_by', 'created_by_name', 'created_at',
            'is_voided', 'void_reason', 'original_transaction', 'refunded_amount',
            'items',
        ]
        read_only_fields = [
            'id', 'reference_number', 'total_amount', 'created_by',
            'created_by_name', 'created_at', 'is_voided', 'void_reason',
            'original_transaction', 'refunded_amount',
        ]


class VoidSerializer(serializers.Serializer):
    """POST /api/v1/transactions/{id}/void/"""
    reason = serializers.CharField(max_length=500)


class RefundCreateSerializer(serializers.Serializer):
    """
    POST /api/v1/transactions/refund/
    Body: { transaction_id, amount, reason }

    Amount-only by design: the cashier/owner types the KES amount being
    handed back to the customer — nothing about which items or how many
    units. The app apportions that amount across the sale's line items
    internally (proportional to each item's remaining refundable value)
    purely to keep stock levels accurate; that math is never surfaced to
    the user. transaction_id is the original SALE being refunded.
    """
    transaction_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=500)