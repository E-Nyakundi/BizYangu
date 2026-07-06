"""
BizYangu — business serializers.
Business setup, profile, staff listing.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Business

User = get_user_model()


class BusinessSetupSerializer(serializers.ModelSerializer):
    """Used for POST /api/v1/business/setup/ — creates the business."""

    class Meta:
        model = Business
        fields = [
            'name', 'type', 'custom_type_name',
            'mpesa_till_number', 'mpesa_paybill_number', 'mpesa_business_shortcode',
            'address', 'currency', 'timezone',
        ]

    def validate(self, attrs):
        if attrs.get('type') == Business.Type.CUSTOM and not attrs.get('custom_type_name'):
            raise serializers.ValidationError(
                {'custom_type_name': 'Andika aina ya biashara yako.'}
            )
        return attrs


class BusinessProfileSerializer(serializers.ModelSerializer):
    """Full business profile — returned on GET /api/v1/business/"""

    subscription_status = serializers.CharField(read_only=True)
    days_remaining = serializers.SerializerMethodField()
    demo_expires_at = serializers.DateTimeField(read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    owner_phone = serializers.CharField(source='owner.phone_number', read_only=True)
    staff_count = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            'id', 'name', 'type', 'custom_type_name',
            'mpesa_till_number', 'mpesa_paybill_number', 'mpesa_business_shortcode',
            'address', 'location_lat', 'location_lng', 'currency', 'timezone',
            'owner_name', 'owner_phone',
            'staff_count',
            'subscription_status', 'days_remaining', 'demo_expires_at',
            'created_at', 'is_active',
        ]
        read_only_fields = [
            'id', 'subscription_status', 'days_remaining', 'demo_expires_at',
            'created_at', 'is_active', 'owner_name', 'owner_phone', 'staff_count',
        ]

    def get_days_remaining(self, obj):
        return obj.days_remaining()

    def get_staff_count(self, obj):
        return obj.staff.filter(is_active=True).count()


class BusinessUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/business/ — update permitted fields only."""

    class Meta:
        model = Business
        fields = [
            'name', 'type', 'custom_type_name',
            'mpesa_till_number', 'mpesa_paybill_number', 'mpesa_business_shortcode',
            'address', 'location_lat', 'location_lng', 'currency', 'timezone',
        ]


class StaffMemberSerializer(serializers.ModelSerializer):
    """Serializer for listing staff members."""

    class Meta:
        model = User
        fields = ['id', 'name', 'phone_number', 'role', 'date_joined', 'is_active']
        read_only_fields = fields