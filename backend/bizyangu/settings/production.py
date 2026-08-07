"""
BizYangu — Production Settings
"""

from .base import *

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')

# Used to build absolute links back to the frontend — currently only the
# staff invite URL (apps/accounts/views.py:invite_staff). Required, no
# default: if this is missing in production, invite links should fail
# loudly at request time, not silently point at localhost.
FRONTEND_URL = config('FRONTEND_URL')

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS').split(',')
CORS_ALLOW_CREDENTIALS = True

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Whitenoise
MIDDLEWARE.insert(2, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Sentry — sentry-sdk has been sitting in requirements/production.txt with
# nothing calling .init(), so nothing was ever actually reported. SENTRY_DSN
# is optional: if it's not set in .env, this whole block is a no-op rather
# than crashing a deploy that hasn't set it up yet.
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        # Errors are always captured; this only controls performance/trace
        # sampling. 20% keeps the free-tier quota from being burned by a
        # single busy duka — raise it later if you need deeper trace data.
        traces_sample_rate=config('SENTRY_TRACES_SAMPLE_RATE', default=0.2, cast=float),
        environment=config('SENTRY_ENVIRONMENT', default='production'),
        send_default_pii=False,
    )
