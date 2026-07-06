"""
BizYangu — JWTCookieAuthentication.
Reads the access token from the httpOnly 'by_access' cookie.
Falls back to the Authorization: Bearer <token> header (for API clients / Postman).
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .services import ACCESS_COOKIE_NAME


class JWTCookieAuthentication(JWTAuthentication):
    """
    Custom authentication backend that reads JWT from httpOnly cookie first,
    then falls back to the Authorization header.
    """

    def authenticate(self, request):
        # 1. Try reading from cookie
        raw_token = request.COOKIES.get(ACCESS_COOKIE_NAME)
        if raw_token:
            try:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token
            except (InvalidToken, TokenError):
                # Cookie token is invalid/expired — try header fallback
                pass

        # 2. Fall back to Authorization: Bearer header
        return super().authenticate(request)