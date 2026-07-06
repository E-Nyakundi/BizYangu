"""
BizYangu — accounts models.
Custom user model (phone-based auth) + OTP tokens.

NOTE: User.business FK is set as a string reference ('business.Business')
to avoid circular import. business app must be migrated first.
"""

import uuid
import hashlib
import secrets
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone_number, name, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number is required.')
        user = self.model(phone_number=phone_number, name=name, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, name, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.OWNER)
        return self.create_user(phone_number, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        MANAGER = 'MANAGER', 'Manager'
        CASHIER = 'CASHIER', 'Cashier'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, unique=True)  # E.164 format
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CASHIER)

    # FK to Business — nullable on creation (user exists before business)
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff',
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['name']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return f'{self.name} ({self.phone_number})'


class OTPToken(models.Model):
    """
    Single-use OTP for phone-based authentication.
    Token is stored hashed — never in plaintext.
    """
    MAX_ATTEMPTS = 3
    EXPIRY_MINUTES = 10

    phone_number = models.CharField(max_length=20)
    token_hash = models.CharField(max_length=64)  # SHA-256 hex
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'OTP token'
        verbose_name_plural = 'OTP tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f'OTP for {self.phone_number}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(minutes=self.EXPIRY_MINUTES)
        super().save(*args, **kwargs)

    @classmethod
    def create_for_phone(cls, phone_number: str) -> tuple['OTPToken', str]:
        """
        Generate a new OTP. Returns (token_instance, plaintext_otp).
        Invalidates any previous unused tokens for this phone.
        """
        cls.objects.filter(phone_number=phone_number, is_used=False).update(is_used=True)
        plaintext = f'{secrets.randbelow(900000) + 100000}'  # 6-digit
        token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        instance = cls.objects.create(phone_number=phone_number, token_hash=token_hash)
        return instance, plaintext

    def verify(self, plaintext: str) -> bool:
        """Check OTP. Increments attempt counter. Returns True if valid."""
        if self.is_used or timezone.now() > self.expires_at:
            return False
        self.attempts += 1
        submitted_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        if submitted_hash == self.token_hash and self.attempts <= self.MAX_ATTEMPTS:
            self.is_used = True
            self.save()
            return True
        self.save()
        return False


class StaffInvite(models.Model):
    """
    A one-time link an OWNER generates to bring a CASHIER/MANAGER onto their
    business. The raw token is never stored — only its SHA-256 hash, same
    pattern as OTPToken above. Whoever holds the raw token (from the
    WhatsApp-shared link) and completes OTP login as themselves can redeem
    it once.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='invites')
    role = models.CharField(max_length=10, choices=User.Role.choices, default=User.Role.CASHIER)
    token_hash = models.CharField(max_length=64, unique=True)  # SHA-256 hex
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='invites_created')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='invite_used')

    class Meta:
        verbose_name = 'staff invite'
        verbose_name_plural = 'staff invites'
        ordering = ['-created_at']

    def __str__(self):
        return f'Invite for {self.business_id} ({self.role})'

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @classmethod
    def create(cls, business_id, role: str, created_by) -> tuple['StaffInvite', str]:
        """Returns (invite_instance, plaintext_token). Only the plaintext is sent to the invitee."""
        from datetime import timedelta
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        instance = cls.objects.create(
            business_id=business_id,
            role=role,
            token_hash=token_hash,
            created_by=created_by,
            expires_at=timezone.now() + timedelta(hours=48),
        )
        return instance, raw_token

    @classmethod
    def redeem(cls, raw_token: str):
        """Looks up an invite by raw token. Returns the instance or None — does not mark it used (caller does that after linking the user)."""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        try:
            return cls.objects.select_related('business').get(token_hash=token_hash)
        except cls.DoesNotExist:
            return None
