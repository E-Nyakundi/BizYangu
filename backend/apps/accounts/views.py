"""
BizYangu — accounts views.
OTP request/verify, token refresh, logout, /me, staff invite.
"""

import hashlib
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPToken, StaffInvite
from .permissions import IsOwner
from .serializers import (
    OTPRequestSerializer,
    OTPVerifySerializer,
    PinSetSerializer,
    PinVerifySerializer,
    UserProfileSerializer,
    UserUpdateSerializer,
)
from .services import (
    clear_auth_cookies,
    get_tokens_for_user,
    send_otp_sms,
    set_auth_cookies,
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
)
from .throttles import OTPRateThrottle
from apps.core.messages import MESSAGES

logger = logging.getLogger(__name__)
User = get_user_model()

# Dev bypass — set DEV_OTP_BYPASS=True in .env to skip SMS and accept '000000'
DEV_OTP_BYPASS = getattr(settings, 'DEV_OTP_BYPASS', False)


# ── OTP request ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPRateThrottle])
def otp_request(request):
    """
    POST /api/v1/auth/otp/request/
    Send a 6-digit OTP to the given phone number.
    Rate limited: 3 requests per phone per hour.
    """
    serializer = OTPRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone = serializer.validated_data['phone_number']

    if DEV_OTP_BYPASS:
        # Create a token record so verify still works, but don't send SMS.
        # Use fixed OTP '000000' stored as a hash.
        OTPToken.create_for_phone(phone)  # creates record; we ignore the plaintext
        logger.warning('[DEV BYPASS] OTP request for %s — use 000000 to verify', phone)
    else:
        token_instance, plaintext_otp = OTPToken.create_for_phone(phone)
        sent = send_otp_sms(phone, plaintext_otp)
        if not sent:
            logger.warning('OTP SMS failed for %s — check AT credentials', phone)

    return Response(
        {'detail': MESSAGES['OTP_SENT'].format(phone=phone)},
        status=status.HTTP_200_OK,
    )


# ── OTP verify ──────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def otp_verify(request):
    """
    POST /api/v1/auth/otp/verify/
    Verify OTP. On success:
    - Creates the user if they don't exist (new user → no business yet).
    - Issues JWT pair as httpOnly cookies.
    - Returns user profile.
    """
    serializer = OTPVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone = serializer.validated_data['phone_number']
    submitted_otp = serializer.validated_data['otp']

    if DEV_OTP_BYPASS:
        # In bypass mode, accept '000000' without checking the DB token
        if submitted_otp != '000000':
            return Response(
                {'detail': MESSAGES['DEV_BYPASS_MODE']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.warning('[DEV BYPASS] OTP verified for %s with bypass pin', phone)
    else:
        # Normal flow — check DB token
        token_qs = OTPToken.objects.filter(
            phone_number=phone,
            is_used=False,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at')

        token_instance = token_qs.first()

        if not token_instance:
            return Response(
                {'detail': MESSAGES['OTP_NOT_FOUND']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if token_instance.attempts >= OTPToken.MAX_ATTEMPTS:
            return Response(
                {'detail': MESSAGES['OTP_TOO_MANY_ATTEMPTS']},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not token_instance.verify(submitted_otp):
            remaining = OTPToken.MAX_ATTEMPTS - token_instance.attempts
            return Response(
                {'detail': MESSAGES['OTP_INVALID_WITH_ATTEMPTS'].format(remaining=remaining)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Get or create user
    user, created = User.objects.get_or_create(
        phone_number=phone,
        defaults={'name': '', 'role': User.Role.OWNER},
    )
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    tokens = get_tokens_for_user(user)
    profile = UserProfileSerializer(user).data

    response = Response(
        {
            'user': profile,
            'is_new_user': created,
        },
        status=status.HTTP_200_OK,
    )
    set_auth_cookies(response, tokens)
    return response


# ── PIN quick re-entry ──────────────────────────────────────────────────────
# A PIN is never checked on its own — pin_verify requires the same httpOnly
# refresh cookie that a normal OTP login already set. That cookie is what
# proves "this device already completed a real OTP login"; the PIN is a
# second factor on top of it, not a replacement for it. Biometric unlock is
# handled entirely client-side (it just gates reading the PIN from secure
# storage before calling this same endpoint) — there is no separate
# biometric path on the backend.

PIN_MAX_ATTEMPTS = 5
PIN_LOCKOUT_MINUTES = 15


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pin_set(request):
    """
    POST /api/v1/auth/pin/set/
    Body: { pin: '1234' }
    Requires a valid (fresh) access token — i.e. called right after a
    normal OTP login, or from Settings while already logged in.
    """
    serializer = PinSetSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    request.user.set_pin(serializer.validated_data['pin'])
    return Response({'detail': MESSAGES['PIN_SET']}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def pin_verify(request):
    """
    POST /api/v1/auth/pin/verify/
    Body: { pin: '1234' }
    No access token required — reads the refresh token from the same
    httpOnly cookie token_refresh uses. On success, rotates both cookies
    exactly like token_refresh does, and returns the user profile like
    otp_verify does, so the frontend can treat this as a drop-in
    alternative login path.
    """
    serializer = PinVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    submitted_pin = serializer.validated_data['pin']

    refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        return Response(
            {'detail': MESSAGES['PIN_SESSION_NOT_FOUND']},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        refresh = RefreshToken(refresh_token)
        user = User.objects.get(id=refresh['user_id'], is_active=True)
    except (TokenError, User.DoesNotExist):
        return Response(
            {'detail': MESSAGES['PIN_SESSION_INVALID']},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.has_pin:
        return Response(
            {'detail': MESSAGES['PIN_NOT_SET']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if user.is_pin_locked:
        return Response(
            {'detail': MESSAGES['PIN_LOCKED']},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not user.check_pin(submitted_pin):
        remaining = user.register_pin_failure(PIN_MAX_ATTEMPTS, PIN_LOCKOUT_MINUTES)
        return Response(
            {
                'detail': MESSAGES['PIN_INCORRECT'].format(remaining=remaining),
                'attempts_remaining': remaining,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    user.clear_pin_failures()

    try:
        refresh.blacklist()
    except TokenError:
        pass  # already blacklisted/rotated concurrently — not fatal

    new_tokens = get_tokens_for_user(user)
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    response = Response(
        {'detail': MESSAGES['PIN_VERIFIED'], 'user': UserProfileSerializer(user).data},
        status=status.HTTP_200_OK,
    )
    set_auth_cookies(response, new_tokens)
    return response


# ── Token refresh ────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh(request):
    """
    POST /api/v1/auth/token/refresh/
    Reads refresh token from httpOnly cookie, issues new access + refresh pair.
    """
    refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        return Response(
            {'detail': MESSAGES['REFRESH_TOKEN_NOT_FOUND']},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        refresh = RefreshToken(refresh_token)
        tokens = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
        refresh.blacklist()
        new_refresh = RefreshToken.for_user(
            User.objects.get(id=refresh['user_id'])
        )
        tokens = {
            'access': str(new_refresh.access_token),
            'refresh': str(new_refresh),
        }
    except (TokenError, User.DoesNotExist) as exc:
        return Response(
            {'detail': MESSAGES['REFRESH_TOKEN_INVALID']},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    response = Response({'detail': MESSAGES['TOKEN_REFRESHED']}, status=status.HTTP_200_OK)
    set_auth_cookies(response, tokens)
    return response


# ── Logout ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    POST /api/v1/auth/logout/
    Blacklist the refresh token and clear auth cookies.
    """
    refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            pass  # Already invalid — that's fine

    response = Response({'detail': MESSAGES['LOGGED_OUT']}, status=status.HTTP_200_OK)
    clear_auth_cookies(response)
    return response


# ── /me ──────────────────────────────────────────────────────────────────────

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    GET  /api/v1/auth/me/   — Current user profile + business demo state.
    PATCH /api/v1/auth/me/  — Update first_name/last_name/email. Used by the
    /setup "About you" step, /join's name-capture step, and Settings.
    """
    if request.method == 'GET':
        return Response(UserProfileSerializer(request.user).data)

    serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(UserProfileSerializer(request.user).data)


# ── Staff invite ──────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOwner])
def invite_staff(request):
    """
    POST /api/v1/auth/invite/
    Body: { role: 'CASHIER' | 'MANAGER' }
    Returns a one-time invite URL. Store the hash; send the URL to the invitee.
    """
    if not request.user.business:
        return Response(
            {'detail': MESSAGES['BUSINESS_NOT_REGISTERED']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    role = request.data.get('role', 'CASHIER')
    if role not in ('CASHIER', 'MANAGER'):
        return Response(
            {'detail': MESSAGES['INVALID_ROLE']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    invite, raw_token = StaffInvite.create(request.user.business.id, role, created_by=request.user)

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    from urllib.parse import quote
    business_name = quote(request.user.business.name)
    invite_url = f"{frontend_url}/join?token={raw_token}&role={role}&business={business_name}"

    return Response({
        'invite_url': invite_url,
        'expires_at': invite.expires_at.isoformat(),
        'role': role,
    }, status=status.HTTP_201_CREATED)


# ── Accept invite ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_invite(request):
    """
    POST /api/v1/auth/join/
    Body: { token }
    The user must already be logged in (completed OTP verification as
    themselves first — the invite link takes them through /login same as
    anyone else, then this endpoint runs). Links the invite's business +
    role onto the *currently authenticated* user; there's no separate
    phone-number field because the phone used to log in already tells us
    who's redeeming it.
    """
    token_raw = request.data.get('token', '')
    if not token_raw:
        return Response({'detail': MESSAGES['TOKEN_AND_PHONE_REQUIRED']}, status=status.HTTP_400_BAD_REQUEST)

    invite = StaffInvite.redeem(token_raw)
    if invite is None:
        return Response({'detail': MESSAGES['INVITE_INVALID']}, status=status.HTTP_404_NOT_FOUND)

    if invite.is_used:
        return Response({'detail': MESSAGES['INVITE_ALREADY_USED']}, status=status.HTTP_400_BAD_REQUEST)

    if invite.is_expired:
        return Response({'detail': MESSAGES['INVITE_EXPIRED']}, status=status.HTTP_400_BAD_REQUEST)

    if request.user.business_id is not None:
        return Response({'detail': MESSAGES['USER_ALREADY_HAS_BUSINESS']}, status=status.HTTP_400_BAD_REQUEST)

    request.user.business = invite.business
    request.user.role = invite.role
    request.user.save(update_fields=['business', 'role'])

    invite.used_at = timezone.now()
    invite.used_by = request.user
    invite.save(update_fields=['used_at', 'used_by'])

    return Response(
        {'detail': MESSAGES['INVITE_ACCEPTED'], 'user': UserProfileSerializer(request.user).data},
        status=status.HTTP_200_OK,
    )