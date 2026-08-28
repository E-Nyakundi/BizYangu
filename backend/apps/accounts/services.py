"""
BizYangu — accounts services.
JWT cookie helpers (httpOnly).
Staff invite token generation.

OTP dispatch moved to apps.messaging.service.send_otp() as of Phase 6.5 —
see BizYangu_Master_Plan.md §3.2/§6.5. It used to live here as
send_otp_sms(), calling Africa's Talking directly; that logic is now the
AfricasTalkingAdapter in apps/messaging/adapters/, reached through a
provider-agnostic interface so a second provider (MobiWave) can be tried
as a fallback instead of OTP delivery depending on a single vendor.
"""

import secrets
import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

User = get_user_model()


def get_tokens_for_user(user) -> dict:
    """Generate a JWT refresh/access pair for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ── httpOnly cookie helpers ─────────────────────────────────────────────────
# Tokens are set as httpOnly cookies — never returned in the response body.
# The frontend does NOT store them in localStorage.

ACCESS_COOKIE_NAME = 'by_access'
REFRESH_COOKIE_NAME = 'by_refresh'

# Mirror SimpleJWT settings
ACCESS_COOKIE_MAX_AGE = int(timedelta(minutes=15).total_seconds())
REFRESH_COOKIE_MAX_AGE = int(timedelta(days=7).total_seconds())


def set_auth_cookies(response, tokens: dict) -> None:
    """
    Attach JWT tokens as httpOnly cookies to a DRF Response.

    SameSite policy:
      - DEBUG=True  (local dev, http://localhost): SameSite=Lax.
      - DEBUG=False (ngrok / production, HTTPS):   SameSite=None.

    Why None in production:
      Capacitor Android loads bundled assets from http://localhost (its internal
      WebView server) and calls the Django backend at a different HTTPS origin.
      SameSite=Lax silently drops cookies on cross-origin XHR, so every API
      request in the APK would 401-loop. SameSite=None; Secure allows the
      cookies to travel on these cross-origin requests.
      SameSite=None is only valid with Secure=True, already guaranteed because
      is_secure is True whenever DEBUG=False.
    """
    is_secure = not settings.DEBUG
    samesite = 'None' if is_secure else 'Lax'

    response.set_cookie(
        ACCESS_COOKIE_NAME,
        tokens['access'],
        max_age=ACCESS_COOKIE_MAX_AGE,
        httponly=True,
        samesite=samesite,
        secure=is_secure,
        path='/',
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        tokens['refresh'],
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        samesite=samesite,
        secure=is_secure,
        path='/api/v1/auth/',  # Refresh cookie only sent to /auth/ routes
    )

def clear_auth_cookies(response) -> None:
    """Remove auth cookies on logout."""
    response.delete_cookie(ACCESS_COOKIE_NAME, path='/')
    response.delete_cookie(REFRESH_COOKIE_NAME, path='/api/v1/auth/')


# NOTE: staff invite token generation now lives on StaffInvite.create()
# in models.py, since it needs to persist a row (this used to be a
# stateless helper before the StaffInvite model existed).