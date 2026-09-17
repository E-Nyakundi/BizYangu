from decimal import Decimal
from rest_framework import serializers

from .models import Customer, CustomerPayment
from .services import customer_balance, oldest_outstanding_sale_date


class CustomerSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    oldest_unpaid_at = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'notes', 'balance', 'oldest_unpaid_at', 'created_at', 'updated_at', 'is_active']
        read_only_fields = ['id', 'balance', 'oldest_unpaid_at', 'created_at', 'updated_at']

    def get_balance(self, obj):
        return str(customer_balance(obj))

    def get_oldest_unpaid_at(self, obj):
        balance = customer_balance(obj)
        if balance <= 0:
            return None
        d = oldest_outstanding_sale_date(obj)
        return d.isoformat() if d else None


class CustomerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'notes']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Name is required.')
        return value


class CustomerPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerPayment
        fields = ['id', 'amount', 'notes', 'created_at']
        read_only_fields = fields


class SettlementCreateSerializer(serializers.Serializer):
    """
    POST /api/v1/customers/{id}/settle/
    Amount-only, mirroring RefundCreateSerializer's design — the owner
    types one KES figure paid toward the balance, nothing about which
    sale(s) it covers.
    """
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
