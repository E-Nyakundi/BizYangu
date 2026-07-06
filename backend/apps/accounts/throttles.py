"""
BizYangu — custom throttles.
OTP request: max 3 per phone number per hour.
General API: per-user rate limiting.
"""

from rest_framework.throttling import SimpleRateThrottle


class OTPRateThrottle(SimpleRateThrottle):
    """
    Max 3 OTP requests per phone number per hour.
    Cache key is based on the phone number from the request body,
    not the user IP (unauthenticated endpoint).
    """
    scope = 'otp'
    rate = '3/hour'

    def get_cache_key(self, request, view):
        phone = request.data.get('phone_number', '')
        if not phone:
            # Fall back to IP if no phone provided (validation will catch it anyway)
            return self.cache_format % {
                'scope': self.scope,
                'ident': self.get_ident(request),
            }
        # Normalise: strip + prefix for cache key
        ident = phone.replace('+', '').replace(' ', '')
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }