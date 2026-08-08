"""
BizYangu — payments serializers.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.core.messages import MESSAGES
from .models import MPesaSTKRequest, MPesaTransaction, SubscriptionPayment, BusinessMpesaCredentials


class STKPushRequestSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        digits = value.strip().replace(' ', '').replace('-', '').replace('+', '')
        if not digits.isdigit() or len(digits) < 9:
            raise serializers.ValidationError(MESSAGES['INVALID_PHONE_NUMBER'])
        return value


class STKRequestSerializer(serializers.ModelSerializer):
    # Normalise backend model status to frontend StkStatus vocabulary:
    # Model uses SUCCESS/TIMEOUT; frontend type uses CONFIRMED/CANCELLED.
    status = serializers.SerializerMethodField()

    # Receipt lives on MPesaTransaction / transaction.mpesa_reference;
    # expose it here so the poll fallback path in sell/page.tsx gets it.
    mpesa_receipt_number = serializers.SerializerMethodField()

    def get_status(self, obj):
        mapping = {
            'SUCCESS': 'CONFIRMED',
            'TIMEOUT': 'CANCELLED',
        }
        return mapping.get(obj.status, obj.status)  # PENDING/FAILED pass through

    def get_mpesa_receipt_number(self, obj):
        # transaction.mpesa_reference is set by process_stk_callback on success.
        if obj.transaction_id:
            return obj.transaction.mpesa_reference or None
        return None

    class Meta:
        model = MPesaSTKRequest
        fields = [
            'id', 'transaction', 'checkout_request_id', 'merchant_request_id',
            'phone_number', 'amount', 'status', 'result_code', 'result_desc',
            'created_at', 'completed_at', 'mpesa_receipt_number',
        ]


class MPesaTransactionSerializer(serializers.ModelSerializer):
    transaction_reference = serializers.CharField(source='transaction.reference_number', default=None, read_only=True)

    class Meta:
        model = MPesaTransaction
        fields = [
            'id', 'transaction', 'transaction_reference', 'mpesa_receipt_number',
            'phone_number', 'amount', 'transaction_date', 'transaction_type',
            'is_matched', 'is_reconciled', 'created_at',
        ]


class ReconcileSerializer(serializers.Serializer):
    mpesa_transaction_id = serializers.UUIDField()
    transaction_id = serializers.UUIDField()


class SubscriptionPaymentRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1'))
    months = serializers.IntegerField(min_value=1, default=1)

    def validate_phone_number(self, value):
        digits = value.strip().replace(' ', '').replace('-', '').replace('+', '')
        if not digits.isdigit() or len(digits) < 9:
            raise serializers.ValidationError(MESSAGES['INVALID_PHONE_NUMBER'])
        return value


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        mapping = {
            'SUCCESS': 'CONFIRMED',
            'TIMEOUT': 'CANCELLED',
        }
        return mapping.get(obj.status, obj.status)

    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'business', 'amount', 'months', 'checkout_request_id',
            'merchant_request_id', 'phone_number', 'mpesa_receipt_number',
            'status', 'result_code', 'result_desc', 'created_at', 'completed_at',
        ]


class BusinessMpesaCredentialsSerializer(serializers.ModelSerializer):
    """
    consumer_secret and passkey are write-only — once saved, an owner
    can overwrite them but never read them back through the API
    (matches how you'd treat any secret in a settings form: you
    re-enter it to change it, you don't get to view it after).
    consumer_key is masked on read down to its last 4 characters so
    an owner can sanity-check "did I save the right app" without the
    full key round-tripping through the API/logs on every GET.
    """
    consumer_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    passkey = serializers.CharField(write_only=True, required=False, allow_blank=True)
    consumer_key = serializers.CharField(required=False, allow_blank=True)
    consumer_key_masked = serializers.SerializerMethodField()
    is_configured = serializers.SerializerMethodField()

    def get_consumer_key_masked(self, obj):
        if not obj.consumer_key:
            return ''
        return f'••••{obj.consumer_key[-4:]}' if len(obj.consumer_key) > 4 else '••••'

    def get_is_configured(self, obj):
        return obj.is_configured()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Never echo the real consumer_key back either — only the
        # masked version. It's not secret like consumer_secret, but
        # there's no reason to send it in full on every GET.
        data.pop('consumer_key', None)
        return data

    class Meta:
        model = BusinessMpesaCredentials
        fields = [
            'till_type', 'shortcode', 'consumer_key', 'consumer_key_masked',
            'consumer_secret', 'passkey', 'env', 'is_active', 'is_configured',
            'verified_at', 'updated_at',
        ]
        read_only_fields = ['is_active', 'verified_at', 'updated_at']