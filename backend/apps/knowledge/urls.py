"""
BizYangu — knowledge base URL configuration.
All routes under /api/v1/knowledge/
"""

from django.urls import path
from . import views

urlpatterns = [
    path('business-types/', views.business_type_list, name='knowledge-business-types'),
    path('taxonomy/<str:business_type_id>/', views.taxonomy_detail, name='knowledge-taxonomy-detail'),
    path('suggestions/<str:category_id>/', views.category_suggestions, name='knowledge-category-suggestions'),
]
