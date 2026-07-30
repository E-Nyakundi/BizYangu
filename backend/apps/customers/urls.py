from django.urls import path
from . import views

urlpatterns = [
    path('', views.customer_list_create, name='customer-list-create'),
    path('<uuid:customer_id>/', views.customer_detail, name='customer-detail'),
    path('<uuid:customer_id>/settle/', views.settle_payment, name='customer-settle'),
]
