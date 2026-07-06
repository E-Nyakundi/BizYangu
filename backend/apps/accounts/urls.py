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

    # JWT management
    path('token/refresh/', views.token_refresh, name='token-refresh'),
    path('logout/', views.logout, name='logout'),

    # User profile
    path('me/', views.me, name='me'),

    # Staff management
    path('invite/', views.invite_staff, name='invite-staff'),
    path('join/', views.accept_invite, name='accept-invite'),
]