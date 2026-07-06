from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_list, name='transaction-list'),
    path('sale/', views.create_sale, name='transaction-sale'),
    path('stock-in/', views.create_stock_in, name='transaction-stock-in'),
    path('adjustment/', views.create_adjustment, name='transaction-adjustment'),
    path('loss/', views.create_adjustment, name='transaction-loss'),
    path('refund/', views.create_refund, name='transaction-refund'),
    path('<uuid:transaction_id>/', views.transaction_detail, name='transaction-detail'),
    path('<uuid:transaction_id>/void/', views.void_transaction, name='transaction-void'),
]
# Phase 1 wiring for transactions
