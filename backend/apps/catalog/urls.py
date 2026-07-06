"""
BizYangu — catalog URL configuration.
All routes under /api/v1/catalog/
"""

from django.urls import path
from . import views

urlpatterns = [
    path('categories/', views.category_list_create, name='category-list-create'),
    path('products/', views.product_list_create, name='product-list-create'),
    path('products/import/', views.product_csv_import, name='product-csv-import'),
    path('products/<uuid:product_id>/', views.product_detail, name='product-detail'),
]