"""
BizYangu — notifications models.
DeviceToken: registers a phone for push delivery (low-stock alerts, etc).
"""

import uuid
from django.db import models
from django.conf import settings


class DeviceToken(models.Model):
    class Platform(models.TextChoices):
        ANDROID = 'ANDROID', 'Android'
        IOS = 'IOS', 'iOS'
        WEB = 'WEB', 'Web'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='device_tokens')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices, default=Platform.ANDROID)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.name} — {self.platform} ({self.token[:12]}…)'


class NotificationLog(models.Model):
    """
    Lightweight audit trail of pushes actually sent (or attempted).
    Useful for debugging "why didn't I get an alert" during the pilot.
    """
    class Kind(models.TextChoices):
        LOW_STOCK = 'LOW_STOCK', 'Low Stock'
        OUT_OF_STOCK = 'OUT_OF_STOCK', 'Out of Stock'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='notification_logs')
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notification_logs',
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTHER)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500)
    recipients_count = models.PositiveIntegerField(default=0)
    sent_successfully = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.kind}: {self.title}'
