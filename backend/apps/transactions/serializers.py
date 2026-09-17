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
    """
    Single line item in a sale. Nested inside SaleCreateSerializer.

    Three shapes are accepted:
      - catalog item:        { product_id, quantity }
      - specific sellable
        form (C10):           { product_unit_id, quantity }
      - not-in-catalog:      { name, unit_price, quantity }   (no product_id)

    product_unit_id rings up a sale against one specific sellable form
    of a product (a stick rather than the pack, a gorogoro rather than
    the bag) — see apps.catalog.models.ProductUnit. The product itself
    is derived from the unit in the view, so product_id is never sent
    alongside it. This mirrors the frontend's addCustomToCart /
    handleConfirmSale split in sell/page.tsx — a custom item has no
    real Product to reference, so it carries its own name + price
    instead of a product_id.
    """
    product_id = serializers.UUIDField(required=False)
    product_unit_id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=200, required=False, allow_blank=False)
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal('0.00')
    )
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))

    def validate(self, attrs):
        has_product = bool(attrs.get('product_id'))
        has_unit = bool(attrs.get('product_unit_id'))
        has_custom = bool(attrs.get('name')) and attrs.get('unit_price') is not None
        provided = sum([has_product, has_unit, has_custom])
        if provided == 0:
            raise serializers.ValidationError(
                'Each item needs product_id, product_unit_id, or both name and '
                'unit_price for a not-in-catalog item.'
            )
        if provided > 1:
            raise serializers.ValidationError(
                'Item cannot combine product_id, product_unit_id, and name/unit_price '
                '— pick exactly one.'
            )
        return attrs


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

    # Split-payment breakdown (item D13). Only meaningful when
    # payment_method == MIXED — for every other method the view derives
    # the single relevant amount from the computed total itself, so these
    # are ignored rather than required in that case. When MIXED, all
    # three that apply must be given and must sum to the computed total;
    # the view does that check once it knows the real total (never trust
    # a client-supplied total for this).
    cash_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    mpesa_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    credit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    # Customer capture for the credit portion of a sale (item D16). Either
    # pass customer_id to bill an existing customer, or customer_name (+
    # optional customer_phone) to get-or-create one on the fly — the same
    # two paths the Creditors tab's "Add customer" flow already supports.
    # Required by the view whenever the resolved credit amount is > 0;
    # optional otherwise.
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    customer_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

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
    # SerializerMethodField instead of source='product.name' — product is
    # nullable for not-in-catalog items, and `source='product.name'` would
    # raise on a None product instead of just returning null.
    product_name = serializers.SerializerMethodField()
    product_sku = serializers.SerializerMethodField()
    # Which specific sellable form was sold (C10) — null for a plain
    # product-level sale or a not-in-catalog item. Lets the frontend show
    # "5 sticks" on a receipt instead of just the parent product's name.
    unit_label = serializers.SerializerMethodField()

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else obj.name

    def get_product_sku(self, obj):
        return obj.product.sku if obj.product_id else None

    def get_unit_label(self, obj):
        return obj.product_unit.get_unit_display() if obj.product_unit_id else None

    class Meta:
        model = TransactionItem
        fields = ['id', 'product', 'product_name', 'product_sku', 'product_unit', 'unit_label',
                  'quantity', 'unit_price', 'cost_price', 'subtotal', 'original_item']
        read_only_fields = ['id', 'product_name', 'product_sku', 'unit_label', 'subtotal', 'original_item']


class TransactionSerializer(serializers.ModelSerializer):
    items = TransactionItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    refunded_amount = serializers.SerializerMethodField()

    def get_refunded_amount(self, obj):
        # Only meaningful on SALE transactions — sum of all non-voided
        # refunds issued against this sale. Frontend uses this to show
        # "KES X refunded" on the transaction detail / history views.
        #
        # Prefer the queryset-level `refunded_total` annotation (see
        # transaction_list/transaction_detail in views.py) — falling back
        # to a live .aggregate() here only covers callers that pass an
        # un-annotated instance directly (e.g. straight from a `.save()`
        # in create_refund/void_transaction). The annotated path is what
        # keeps list/detail endpoints at a fixed query count regardless of
        # how many rows are on the page.
        if obj.type != Transaction.Type.SALE:
            return None
        if hasattr(obj, 'refunded_total'):
            # Annotated queryset — Sum(...) is None when there are no
            # refunds (not 0), so check presence of the attribute itself,
            # not its truthiness, or every zero-refund row would silently
            # fall through to the per-row query below and reintroduce
            # the N+1 this annotation exists to avoid.
            if obj.refunded_total is None:
                return '0.00'
            return str(obj.refunded_total.quantize(Decimal('0.01')))
        total = obj.refunds.filter(is_voided=False).aggregate(
            total=Sum('total_amount')
        )['total']
        return str(total.quantize(Decimal('0.01'))) if total else '0.00'

    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'reference_number', 'total_amount',
            'payment_method', 'payment_status', 'mpesa_reference',
            'cash_amount', 'mpesa_amount', 'credit_amount', 'customer',
            'notes', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'is_voided', 'void_reason', 'original_transaction', 'refunded_amount',
            'items',
        ]
        read_only_fields = [
            'id', 'reference_number', 'total_amount', 'created_by',
            'created_by_name', 'created_at', 'updated_at', 'is_voided', 'void_reason',
            'original_transaction', 'refunded_amount',
            'cash_amount', 'mpesa_amount', 'credit_amount',
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


# ── Reconciliation queue (Phase 9.2, minimal — pilot-path plan Phase 2) ────────

class UnreconciledGroupSerializer(serializers.Serializer):
    """
    Read-only shape for one row of GET /api/v1/transactions/unreconciled/.
    One row per distinct freeform item name, not per sale — five separate
    sales of "Blue Band 500g" collapse into a single queue entry with
    item_count=5, so the owner resolves it once instead of five times.
    """
    name = serializers.CharField()
    item_count = serializers.IntegerField()
    total_quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    first_sold_at = serializers.DateTimeField()
    last_sold_at = serializers.DateTimeField()


class ResolveUnreconciledSerializer(serializers.Serializer):
    """
    POST /api/v1/transactions/unreconciled/resolve/
    Body: { name, product_id } to link to an existing catalog product, or
    { name, new_product: {...} } to create one from the queue entry.
    Exactly one of product_id / new_product must be given — never both,
    never neither. `new_product` is validated against catalog's own
    ProductCreateSerializer in the view, so it follows the exact same
    rules (positive price, valid unit, etc.) as adding a product by hand.
    """
    name = serializers.CharField(max_length=200)
    product_id = serializers.UUIDField(required=False)
    new_product = serializers.DictField(required=False)

    def validate(self, attrs):
        has_product = bool(attrs.get('product_id'))
        has_new = bool(attrs.get('new_product'))
        if has_product == has_new:
            raise serializers.ValidationError(
                'Provide exactly one of product_id or new_product — pick an '
                'existing product, or create a new one, not both or neither.'
            )
        return attrs