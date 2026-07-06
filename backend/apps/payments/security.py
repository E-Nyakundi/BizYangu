"""
BizYangu — Safaricom callback IP allowlisting.

The STK Push / C2B webhook endpoints have to be public (Safaricom
calls them with no auth header at all), so the only thing standing
between the internet and `payments.views` is this IP check.

Default allowlist is Safaricom's published Daraja callback ranges.
During sandbox development behind ngrok, Safaricom's sandbox calls
still originate from these same ranges, so this should not need to be
disabled for local testing — only widened if Safaricom changes their
IPs (check https://developer.safaricom.co.ke for the current list).

Set MPESA_CALLBACK_IP_ALLOWLIST_DISABLED=True in .env ONLY for local
debugging with a tool like Postman that won't come from a Safaricom
IP — never leave it disabled against a real deployment.
"""

import functools
import ipaddress
import logging

from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

# Safaricom Daraja published callback source ranges (sandbox + production).
DEFAULT_ALLOWLIST = [
    '196.201.214.200/29',
    '196.201.214.206/32',
    '196.201.213.114/32',
    '196.201.213.44/32',
    '196.201.212.127/32',
    '196.201.212.138/32',
    '196.201.212.129/32',
    '196.201.212.136/32',
]


def _client_ip(request) -> str:
    # Safaricom calls us directly, but if you're behind ngrok/nginx the
    # real source IP shows up in X-Forwarded-For instead of REMOTE_ADDR.
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _is_allowed(ip: str) -> bool:
    allowlist = getattr(settings, 'MPESA_CALLBACK_IP_ALLOWLIST', None) or DEFAULT_ALLOWLIST
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for cidr in allowlist:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def safaricom_ip_required(view_func):
    """
    Decorator for public Daraja webhook views. Rejects anything not
    coming from a Safaricom IP with a 403 — logged, not raised, since
    these endpoints have no other auth and we don't want to leak why.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if getattr(settings, 'MPESA_CALLBACK_IP_ALLOWLIST_DISABLED', False):
            return view_func(request, *args, **kwargs)

        ip = _client_ip(request)
        if not _is_allowed(ip):
            logger.warning('Rejected M-Pesa callback from non-Safaricom IP: %s', ip)
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        return view_func(request, *args, **kwargs)

    return wrapper
