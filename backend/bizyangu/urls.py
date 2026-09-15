"""
BizYangu — URL Configuration
"""

from decouple import config
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


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
]
