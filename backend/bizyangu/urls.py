"""
BizYangu — URL Configuration
"""

from decouple import config
from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.http import JsonResponse
from django.views.static import serve as serve_media


def health_check(request):
    return JsonResponse({
        'status': 'ok',
        'service': 'BizYangu API',
        'version': '0.1.0',
    })


# The default /admin/ path is the first thing every scanner and bot tries.
# ADMIN_URL_PATH lets you move it via .env without touching code — set
# ADMIN_URL_PATH=some-long-random-slug/ in production. Defaults back to
# 'admin/' for local dev so nothing breaks if it's unset.
ADMIN_URL_PATH = config('ADMIN_URL_PATH', default='admin/')

urlpatterns = [
    path(ADMIN_URL_PATH, admin.site.urls),
    path('api/v1/health/', health_check, name='health-check'),

    # Auth
    path('api/v1/auth/', include('apps.accounts.urls')),

    # Core
    path('api/v1/business/', include('apps.business.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/transactions/', include('apps.transactions.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/customers/', include('apps.customers.urls')),
    path('api/v1/knowledge/', include('apps.knowledge.urls')),
    path('api/v1/products/', include('apps.products.urls')),
    path('api/v1/sync/', include('apps.sync.urls')),
]

# Product photos (and any other user-uploaded MEDIA_ROOT file) — nothing
# in this project serves /media/ in production: WhiteNoise (already
# wired in for STATIC_URL above) deliberately only serves build-time
# static assets, never MEDIA_ROOT, and no static() helper for MEDIA_URL
# was ever added outside DEBUG. That gap was invisible until the
# product-photo feature actually needed to read an uploaded file back —
# ImageField uploads still succeeded and the DB/API happily returned a
# /media/... URL, it just 404'd for every viewer. django.views.static.serve
# is Django's own plain file-serving view — normally dev-only advice, but
# fine for this volume of traffic (small-business product photos, not a
# CDN-scale media library) and works whether or not the reverse proxy
# (Caddy) is also configured to intercept /media/ first, since Caddy
# routing to this container for anything it doesn't shortcut is the
# existing setup already relied on for every other path here.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve_media, {'document_root': settings.MEDIA_ROOT}),
]
