"""
BizYangu — accounts URL configuration.
All routes under /api/v1/auth/
"""

from django.urls import path
from . import views

urlpatterns = [
    # OTP auth
    path('otp/request/', views.otp_request, name='otp-request'),
    path('otp/verify/', views.otp_verify, name='otp-verify'),

    # Google sign-in — see accounts.views.google_signin
    path('google/', views.google_signin, name='google-signin'),

    # PIN quick re-entry (requires a prior OTP login on this device — see views.pin_verify)
    path('pin/set/', views.pin_set, name='pin-set'),
    path('pin/verify/', views.pin_verify, name='pin-verify'),

    # JWT management
    path('token/refresh/', views.token_refresh, name='token-refresh'),
    path('logout/', views.logout, name='logout'),

    # User profile
    path('me/', views.me, name='me'),

    # Staff management
    path('invite/', views.invite_staff, name='invite-staff'),
    path('join/', views.accept_invite, name='accept-invite'),
]