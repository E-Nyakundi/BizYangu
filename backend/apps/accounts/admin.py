"""
BizYangu — accounts admin.

Added ahead of pilot launch. Deliberately a plain ModelAdmin, not a full
django.contrib.auth UserAdmin — this app authenticates by OTP, not
password, so there's no password-change form to wire up. This gives you
"who is this phone number, what business/role are they" lookup during
support, and a way to deactivate an account (is_active) without a DB
query. It does not expose OTPToken or StaffInvite — those store hashed
values only and have no support value in admin.
"""

from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'phone_number', 'name', 'role', 'business', 'is_active',
        'is_staff', 'date_joined', 'last_login',
    )
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('phone_number', 'name', 'business__name')
    readonly_fields = ('id', 'date_joined', 'last_login', 'password')
    ordering = ('-date_joined',)
