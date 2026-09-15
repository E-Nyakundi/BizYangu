"""
BizYangu — shared product identity serializers.
"""

from rest_framework import serializers

from .models import GlobalProduct


class GlobalProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalProduct
        fields = [
            'id', 'barcode', 'name', 'brand', 'category', 'unit',
            'status', 'source', 'confirmation_count', 'conflict_count',
        ]
        read_only_fields = fields


class ResolveBarcodeRequestSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=100)


class CreateCandidateSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    brand = serializers.CharField(max_length=100, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    unit = serializers.CharField(max_length=20, required=False, allow_blank=True)


class VerifyGlobalProductSerializer(serializers.Serializer):
    matches_existing = serializers.BooleanField()
    # Only read when matches_existing=False — see services.record_verification.
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    brand = serializers.CharField(max_length=100, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    unit = serializers.CharField(max_length=20, required=False, allow_blank=True)
