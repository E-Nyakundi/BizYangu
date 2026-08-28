"""
BizYangu — Base Settings
Shared across all environments.
"""

from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'channels',

    # BizYangu apps
    'apps.accounts',
    'apps.business',
    'apps.catalog',
    'apps.transactions',
    'apps.inventory',
    'apps.payments',
    'apps.reports',
    'apps.notifications',
    'apps.customers',
    'apps.knowledge',
    'apps.messaging',  # Phase 6.5 — provider-agnostic SMS/OTP layer
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bizyangu.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bizyangu.wsgi.application'
ASGI_APPLICATION = 'bizyangu.asgi.application'

# Database (overridden per environment)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='bidness'),
        'USER': config('DB_USER', default='lewis'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalisation
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.accounts.authentication.JWTCookieAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    # General-purpose throttling. This is on top of, not instead of, the
    # OTPRateThrottle already applied to otp_request — that one is tighter
    # and phone-number-scoped. These are the backstop for every other
    # endpoint: a logged-in user hammering /reports/period/ or a stray
    # script retrying /transactions/sale/ shouldn't be able to run the DB
    # or M-Pesa API ragged. Tune 'sustained_user'/'burst_anon' in .env-driven
    # settings later if a real duka's normal usage ever gets close to these.
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.ScopedRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '300/minute',
        'anon': '30/minute',
        'burst_write': '30/minute',
    },
}

# SimpleJWT
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Channels — Redis channel layer
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://localhost:6379/0')],
        },
    },
}

# Celery
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_TIMEZONE = 'Africa/Nairobi'

# STK Push timeout sweep (Phase 1 of the pilot-path plan). Daraja's own
# STK prompt itself expires client-side in ~60-100s, but a dropped
# tunnel or network hiccup means the callback that would normally tell
# us that can simply never arrive — leaving a sale sitting PENDING with
# stock already deducted, with no automatic way out. This periodic task
# (apps.payments.tasks.check_stale_stk_requests) sweeps for exactly that
# and auto-voids anything still PENDING past this many minutes, reusing
# the same void-and-restore-stock logic the real FAILED callback uses.
# Padded well past Daraja's own prompt window to comfortably avoid
# voiding a sale where the customer is just slow to respond.
STK_TIMEOUT_MINUTES = config('STK_TIMEOUT_MINUTES', default=10, cast=int)

CELERY_BEAT_SCHEDULE = {
    'check-stale-stk-requests': {
        'task': 'apps.payments.tasks.check_stale_stk_requests',
        # Sweep every 5 minutes — frequent enough that a stuck sale
        # doesn't sit blocking stock for long, infrequent enough not to
        # hammer the DB with a query that will almost always find nothing.
        'schedule': 300.0,
    },
}

# Cache — this was previously UNSET, which meant Django silently fell back
# to its default LocMemCache: per-process, in-memory, not shared across
# worker processes. Every DRF throttle (OTPRateThrottle, and the
# UserRateThrottle/AnonRateThrottle/ScopedRateThrottle added for general
# API rate limiting) tracks its counters through Django's cache framework —
# with LocMemCache, a rate meant to be "300/minute per user" was actually
# "300/minute per user PER WORKER PROCESS", i.e. silently multiplied by
# however many gunicorn/uwsgi workers are running. Pointing this at the
# same Redis instance already used for Channels/Celery makes throttle
# counts (and any other cache.get/set call anywhere in the app) actually
# shared across every worker and every process.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
    }
}

# Africa's Talking
AT_USERNAME = config('AT_USERNAME', default='sandbox')
AT_API_KEY = config('AT_API_KEY', default='')
# Blank until a Kenyan Sender ID registration is approved (see
# BizYangu_Path_to_Pilot.md). Blank = AT's shared default sender,
# unchanged from before this setting existed.
AT_SENDER_ID = config('AT_SENDER_ID', default='')

# MobiWave (Phase 6.5 — second SMS provider)
# NOTE: request/response shape in apps/messaging/adapters/mobiwave.py is
# a placeholder pending MobiWave's real API docs — see that file's
# docstring. Leave MOBIWAVE_API_KEY unset until those docs are in hand;
# an unset key makes the adapter fail cleanly and NotificationService
# will skip straight to the next provider in SMS_PROVIDER_PRIORITY.
MOBIWAVE_API_KEY = config('MOBIWAVE_API_KEY', default='')
MOBIWAVE_SENDER_ID = config('MOBIWAVE_SENDER_ID', default='')

# Phase 6.5 — SMS provider priority/failover order. NotificationService
# (apps/messaging/service.py) tries each in order until one succeeds.
# Defaults to AT-only so any environment that hasn't set this yet behaves
# exactly like before this phase existed. Once MobiWave's real API is
# confirmed working, change this to e.g. ['mobiwave', 'africastalking']
# to make it primary with AT as fallback — a settings change, not a code
# change.
SMS_PROVIDER_PRIORITY = config(
    'SMS_PROVIDER_PRIORITY',
    default='africastalking',
    cast=lambda v: [name.strip() for name in v.split(',') if name.strip()],
)

# M-Pesa Daraja
MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='')
MPESA_ENV = config('MPESA_ENV', default='sandbox')  # 'sandbox' or 'production'
# Local-debugging escape hatch ONLY (e.g. testing webhooks with Postman).
# Never set this True against a real deployment — see apps/payments/security.py
MPESA_CALLBACK_IP_ALLOWLIST_DISABLED = config(
    'MPESA_CALLBACK_IP_ALLOWLIST_DISABLED', default=False, cast=bool,
)

# M-Pesa Daraja — company shortcode (BizYangu's OWN subscription
# billing, e.g. Ksh 800/month from each business owner to us). This is
# a completely separate Daraja app from MPESA_* above, which is the
# shared shortcode businesses use to receive payment from THEIR
# customers. Keeping them separate means a mistake in one flow (wrong
# shortcode, revoked credentials) can never silently misroute money
# meant for the other.
MPESA_COMPANY_CONSUMER_KEY = config('MPESA_COMPANY_CONSUMER_KEY', default='')
MPESA_COMPANY_CONSUMER_SECRET = config('MPESA_COMPANY_CONSUMER_SECRET', default='')
MPESA_COMPANY_SHORTCODE = config('MPESA_COMPANY_SHORTCODE', default='')
MPESA_COMPANY_PASSKEY = config('MPESA_COMPANY_PASSKEY', default='')
MPESA_COMPANY_CALLBACK_URL = config('MPESA_COMPANY_CALLBACK_URL', default='')
MPESA_COMPANY_ENV = config('MPESA_COMPANY_ENV', default='sandbox')  # 'sandbox' or 'production'

# Fernet key encrypting BusinessMpesaCredentials.consumer_secret/passkey
# at rest (see apps/payments/fields.py). Deliberately separate from
# SECRET_KEY so rotating one never breaks the other. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MPESA_CREDENTIALS_ENCRYPTION_KEY = config('MPESA_CREDENTIALS_ENCRYPTION_KEY', default='')

# Firebase Cloud Messaging — push notifications (low-stock alerts).
# Paste the full service-account JSON as a single-line string in .env.
# Left empty until you create a Firebase project; notifications app
# fails soft (logs + no-op) when this isn't set.
FCM_SERVICE_ACCOUNT_JSON = config('FCM_SERVICE_ACCOUNT_JSON', default='')



from corsheaders.defaults import default_headers


CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'ngrok-skip-browser-warning',  # ← this is all that's missing
]

# Demo period (days)
DEMO_PERIOD_DAYS = 14
# Dev OTP bypass — never True in production
DEV_OTP_BYPASS = config('DEV_OTP_BYPASS', default=False, cast=bool)