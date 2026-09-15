"""
BizYangu — shared product identity URL configuration.
All routes under /api/v1/products/
"""

from django.urls import path
from . import views

urlpatterns = [
    path('resolve-barcode/', views.resolve_barcode, name='products-resolve-barcode'),
    path('candidates/', views.create_candidate, name='products-create-candidate'),
    path('<str:barcode>/verify/', views.verify_global_product, name='products-verify'),
]
