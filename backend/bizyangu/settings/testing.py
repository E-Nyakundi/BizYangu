"""
BizYangu — Testing settings (not shipped). sqlite in-memory DB so C10's
sale-flow integration can be exercised end-to-end via DRF's APIClient
without a Postgres instance, same approach as the earlier C10 backend
model/API passes.
"""
from .development import *  # noqa

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# No Redis in this sandbox — local-memory cache is enough for a functional
# pass (this only backs DRF's ScopedRateThrottle here, nothing else).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
