"""
BizYangu — business URL configuration.
All routes under /api/v1/business/
"""

from django.urls import path
from . import views

urlpatterns = [
    path('setup/', views.business_setup, name='business-setup'),
    path('', views.business_detail, name='business-detail'),
    path('users/', views.staff_list, name='staff-list'),
    path('users/<uuid:user_id>/', views.staff_remove, name='staff-remove'),
]