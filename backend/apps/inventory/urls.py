"""
BizYangu — inventory URL configuration.
All routes under /api/v1/inventory/
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.stock_levels, name='stock-levels'),
    path('low-stock/', views.low_stock, name='low-stock'),
    path('movements/', views.movement_list, name='movement-list'),
    path('count/', views.submit_stock_count, name='stock-count'),
    path('repackage/', views.repackage_list_create, name='repackage-list-create'),
]