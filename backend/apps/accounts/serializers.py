"""
BizYangu — accounts serializers.
OTP request/verify, user profile, staff invite.
"""

import re
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.core.messages import MESSAGES
from .models import OTPToken

User = get_user_model()

E164_REGEX = re.compile(r'^\+254[0-9]{9}$')


def validate_kenyan_phone(value: str) -> str:
    """Normalise and validate a Kenyan phone number to E.164 format."""
    v = value.strip()
    # Accept 07XX or +2547XX — normalise to +2547XX
    if v.startswith('07') or v.startswith('01'):
        v = '+254' + v[1:]
    if not E164_REGEX.match(v):
        raise serializers.ValidationError(MESSAGES['INVALID_PHONE_NUMBER_FORMAT'])
    return v


class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        return validate_kenyan_phone(value)


class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_phone_number(self, value):
        return validate_kenyan_phone(value)

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('OTP lazima iwe nambari 6.')
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    business_id = serializers.UUIDField(source='business.id', read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    subscription_status = serializers.CharField(
        source='business.subscription_status', read_only=True
    )
    days_remaining = serializers.SerializerMethodField()
    demo_expires_at = serializers.DateTimeField(
        source='business.demo_expires_at', read_only=True
    )

    class Meta:
        model = User
        fields = [
            'id', 'phone_number', 'name', 'role',
            'business_id', 'business_name',
            'subscription_status', 'days_remaining', 'demo_expires_at',
            'date_joined',
        ]
        read_only_fields = fields

    def get_days_remaining(self, obj):
        if obj.business:
            return obj.business.days_remaining()
        return None


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['name']