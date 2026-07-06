"""
BizYangu — payments serializers.
"""

from rest_framework import serializers

from apps.core.messages import MESSAGES
from .models import MPesaSTKRequest, MPesaTransaction


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