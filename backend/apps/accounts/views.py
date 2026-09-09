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
    GoogleSignInSerializer,
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
    set_auth_cookies,
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
)
from .throttles import OTPRateThrottle
from apps.core.messages import MESSAGES
from apps.messaging.service import send_otp  # Phase 6.5 — replaces send_otp_sms

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
        sent = send_otp(phone, plaintext_otp)
        if not sent:
            logger.warning(
                'OTP SMS failed for %s — all configured providers in '
                'SMS_PROVIDER_PRIORITY failed, see SMSDeliveryLog for '
                'per-provider detail', phone,
            )

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
    - Issues JWT pair as httpOnly cookies (web/Capacitor), and also in
      the response body's 'tokens' key (Flutter, Phase 15 — no cookie
      jar to rely on, see BizYangu_Master_Plan.md Phase 15).
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

    # Phase 15 — Flutter has no cookie jar to auto-attach httpOnly cookies
    # the way a browser/Capacitor webview does, so tokens are also
    # returned in the body here. Web/Capacitor clients keep working
    # exactly as before via the cookie set below; they simply ignore
    # this extra 'tokens' key. Flutter reads it, stores both values in
    # flutter_secure_storage, and attaches the access token as
    # Authorization: Bearer <token> on every subsequent request — see
    # BizYangu_Master_Plan.md Phase 15 for the full rationale.
    response = Response(
        {
            'user': profile,
            'is_new_user': created,
            'tokens': tokens,
        },
        status=status.HTTP_200_OK,
    )
    set_auth_cookies(response, tokens)
    return response


# ── Google sign-in ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def google_signin(request):
    """
    POST /api/v1/auth/google/
    Body: { id_token: '...' }
    Verifies a Google ID token (from Google Identity Services on web, or
    the native Google Sign-In SDK inside the Capacitor/Flutter shells),
    then get-or-creates a user by the token's stable 'sub' claim and logs
    them in exactly like otp_verify — same cookie-setting, same response
    shape (user / is_new_user / tokens) — so the frontend can treat this
    as a second entry point into the same post-login flow (goToApp /
    /setup redirect), not a separate auth system.

    Unlike OTP users, a Google user has no phone_number at all until they
    add one later from Settings — see the accounts.User docstring note on
    phone_number being nullable specifically for this path.
    """
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    serializer = GoogleSignInSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    raw_token = serializer.validated_data['id_token']

    client_ids = getattr(settings, 'GOOGLE_OAUTH_CLIENT_IDS', [])
    if not client_ids:
        logger.error('Google sign-in attempted but GOOGLE_OAUTH_CLIENT_IDS is not configured')
        return Response(
            {'detail': MESSAGES['GOOGLE_SIGNIN_NOT_CONFIGURED']},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    idinfo = None
    last_error = None
    # A token is minted for exactly one audience (one OAuth client), so try
    # each configured client ID (web, Android) until one verifies.
    for client_id in client_ids:
        try:
            idinfo = google_id_token.verify_oauth2_token(
                raw_token, google_requests.Request(), client_id,
            )
            break
        except ValueError as exc:
            last_error = exc
            continue

    if idinfo is None:
        logger.warning('Google ID token verification failed: %s', last_error)
        return Response(
            {'detail': MESSAGES['GOOGLE_SIGNIN_INVALID_TOKEN']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not idinfo.get('email_verified', False):
        return Response(
            {'detail': MESSAGES['GOOGLE_SIGNIN_EMAIL_NOT_VERIFIED']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    google_sub = idinfo['sub']
    email = idinfo.get('email', '')

    user = User.objects.filter(google_sub=google_sub).first()
    created = False

    if user is None:
        # Not seen this Google account before. If the email already
        # belongs to an existing (e.g. OTP-created) user, link this
        # Google account onto it instead of creating a duplicate person —
        # same phone number, same business, now also sign-in-able via
        # Google. Otherwise create a brand-new user, same shape as a
        # brand-new OTP user (no business yet → frontend sends them to
        # /setup).
        user = User.objects.filter(email=email).first() if email else None
        if user is None:
            user = User.objects.create_user(
                phone_number=None,
                name=idinfo.get('name', '') or '',
                first_name=idinfo.get('given_name', '') or '',
                last_name=idinfo.get('family_name', '') or '',
                email=email or None,
                role=User.Role.OWNER,
            )
            created = True
        user.google_sub = google_sub
        user.save(update_fields=['google_sub'])

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    tokens = get_tokens_for_user(user)
    profile = UserProfileSerializer(user).data

    response = Response(
        {
            'user': profile,
            'is_new_user': created,
            'tokens': tokens,  # Phase 15 — see otp_verify's comment
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
    Body: { pin: '1234' } — plus { refresh: '...' } for clients with no
    cookie jar (Flutter, Phase 15).
    No access token required — reads the refresh token from the same
    httpOnly cookie token_refresh uses, falling back to the body's
    'refresh' field. On success, rotates both cookies exactly like
    token_refresh does (and also returns the new pair in the body's
    'tokens' key), and returns the user profile like otp_verify does, so
    the frontend can treat this as a drop-in alternative login path.
    """
    serializer = PinVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    submitted_pin = serializer.validated_data['pin']

    # Phase 15 — Flutter has no cookie to read the refresh token from, so
    # it sends it in the request body instead: {"pin": "...", "refresh":
    # "..."}. Cookie is checked first so web/Capacitor clients (which
    # never send this field) are completely unaffected.
    refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME) or request.data.get('refresh')
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
        {
            'detail': MESSAGES['PIN_VERIFIED'],
            'user': UserProfileSerializer(user).data,
            'tokens': new_tokens,  # Phase 15 — see otp_verify's comment
        },
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
    Reads refresh token from httpOnly cookie, or from the request body's
    'refresh' field for clients with no cookie jar (Flutter, Phase 15).
    Issues new access + refresh pair, returned as cookies AND in the
    response body's 'tokens' key.
    """
    # Phase 15 — Flutter sends the refresh token in the body instead of a
    # cookie: {"refresh": "..."}. Checked after the cookie so web/
    # Capacitor behavior is unchanged.
    refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME) or request.data.get('refresh')
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

    response = Response(
        {'detail': MESSAGES['TOKEN_REFRESHED'], 'tokens': tokens},  # Phase 15
        status=status.HTTP_200_OK,
    )
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