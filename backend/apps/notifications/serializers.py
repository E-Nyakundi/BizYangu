"""
BizYangu — notifications serializers.
"""

from rest_framework import serializers
from .models import DeviceToken, NotificationLog


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'platform', 'is_active', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'created_at', 'last_used_at']


class NotificationLogSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = NotificationLog
        fields = [
            'id', 'kind', 'title', 'body', 'product', 'product_name',
            'recipients_count', 'sent_successfully', 'created_at',
        ]
