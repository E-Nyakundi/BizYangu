"""
BizYangu — business models.
Business profile, settings, demo/subscription control.

This app must be migrated BEFORE accounts (accounts.User has a FK here).
"""

import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings


class Business(models.Model):
    class Type(models.TextChoices):
        DUKA = 'DUKA', 'Duka'
        HARDWARE = 'HARDWARE', 'Hardware'
        BOUTIQUE = 'BOUTIQUE', 'Boutique'
        STATIONERY = 'STATIONERY', 'Stationery'
        PHARMACY = 'PHARMACY', 'Pharmacy'
        AGROVET = 'AGROVET', 'Agrovet'
        CUSTOM = 'CUSTOM', 'Custom'

    class SubscriptionStatus(models.TextChoices):
        DEMO = 'DEMO', 'Demo'
        ACTIVE = 'ACTIVE', 'Active'
        EXPIRED = 'EXPIRED', 'Expired'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.DUKA)
    custom_type_name = models.CharField(max_length=100, blank=True)

    # M-Pesa
    mpesa_till_number = models.CharField(max_length=20, blank=True)
    mpesa_paybill_number = models.CharField(max_length=20, blank=True)
    mpesa_business_shortcode = models.CharField(max_length=20, blank=True)

    # Owner (set after user is created)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_businesses',
        null=True,
        blank=True,
    )

    address = models.TextField(blank=True)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    currency = models.CharField(max_length=3, default='KES')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Demo / subscription control
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.DEMO,
    )
    demo_started_at = models.DateTimeField(null=True, blank=True)
    demo_expires_at = models.DateTimeField(null=True, blank=True)
    demo_period_days = models.PositiveIntegerField(default=14)
    subscribed_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = 'business'
        verbose_name_plural = 'businesses'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.demo_started_at:
            from datetime import timedelta
            self.demo_started_at = timezone.now()
            days = self.demo_period_days or getattr(settings, 'DEMO_PERIOD_DAYS', 14)
            self.demo_expires_at = self.demo_started_at + timedelta(days=days)
        super().save(*args, **kwargs)

    def is_demo_expired(self) -> bool:
        if self.subscription_status == self.SubscriptionStatus.ACTIVE:
            return False
        if self.subscription_status == self.SubscriptionStatus.EXPIRED:
            return True
        # DEMO state — check clock
        if self.demo_expires_at:
            return timezone.now() >= self.demo_expires_at
        return False

    def days_remaining(self) -> int | None:
        if self.subscription_status != self.SubscriptionStatus.DEMO:
            return None
        if not self.demo_expires_at:
            return None
        delta = self.demo_expires_at - timezone.now()
        return max(0, delta.days)
