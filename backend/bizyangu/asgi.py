"""
BizYangu ASGI config — Django Channels entry point.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bizyangu.settings.development')

# get_asgi_application() must be called before any models are imported,
# so do it here before the consumer import below.
django_asgi_app = get_asgi_application()

from apps.payments.ws_auth import JWTCookieAuthMiddleware
from apps.payments.consumers import MPesaConsumer
from apps.reports.consumers import DashboardConsumer

websocket_urlpatterns = [
    re_path(r'^ws/mpesa/(?P<business_id>[^/]+)/$', MPesaConsumer.as_asgi()),
    re_path(r'^ws/dashboard/(?P<business_id>[^/]+)/$', DashboardConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTCookieAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})