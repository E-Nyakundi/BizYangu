"""
BizYangu — Channels middleware to authenticate WebSocket connections
using the same httpOnly JWT cookie the REST API uses.

Channels' built-in AuthMiddlewareStack only understands Django
sessions, which this project doesn't use for API auth (SimpleJWT in
an httpOnly cookie instead — see apps/accounts/authentication.py).
This middleware parses that cookie out of the raw ASGI headers and
attaches the resolved user to scope['user'], same as request.user on
the HTTP side.
"""

from http.cookies import SimpleCookie

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.accounts.services import ACCESS_COOKIE_NAME


@database_sync_to_async
def _get_user_from_token(raw_token: str):
    try:
        auth = JWTAuthentication()
        validated = auth.get_validated_token(raw_token)
        return auth.get_user(validated)
    except (InvalidToken, TokenError):
        return AnonymousUser()


class JWTCookieAuthMiddleware:
    """ASGI middleware — wraps the inner application (URLRouter)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get('headers') or [])
        cookie_header = headers.get(b'cookie', b'').decode()
        cookie = SimpleCookie()
        cookie.load(cookie_header)

        token_morsel = cookie.get(ACCESS_COOKIE_NAME)
        if token_morsel:
            scope['user'] = await _get_user_from_token(token_morsel.value)
        else:
            scope['user'] = AnonymousUser()

        return await self.app(scope, receive, send)
