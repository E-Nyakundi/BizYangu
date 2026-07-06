"""
BizYangu — Development Settings
"""

from .base import *

# Read from .env so we can set DEBUG=False when testing via ngrok + Capacitor.
# DEBUG=True  → local browser dev (http://localhost:3000)
# DEBUG=False → APK testing through ngrok (HTTPS, SameSite=None cookies needed)
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000').split(',')
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000'
).split(',')

# Whitenoise for static files in dev
INSTALLED_APPS.insert(1, 'whitenoise.runserver_nostatic')
MIDDLEWARE.insert(2, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Django debug toolbar (optional)
INTERNAL_IPS = ['127.0.0.1']