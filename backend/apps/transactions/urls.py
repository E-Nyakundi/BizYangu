from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_list, name='transaction-list'),
    path('sale/', views.create_sale, name='transaction-sale'),
    path('stock-in/', views.create_stock_in, name='transaction-stock-in'),
    path('adjustment/', views.create_adjustment, name='transaction-adjustment'),
    path('loss/', views.create_adjustment, name='transaction-loss'),
    path('refund/', views.create_refund, name='transaction-refund'),
    path('unreconciled/', views.unreconciled_list, name='transaction-unreconciled-list'),
    path('unreconciled/resolve/', views.unreconciled_resolve, name='transaction-unreconciled-resolve'),
    # Item D12 — receipt serial lookup. Reuses reference_number (already
    # generated at sale time, already unique per business) rather than a
    # new field; scoped internally for pilot per the architecture note in
    # the pre-pilot doc — see receipt_lookup() for why.
    path('receipt/<str:reference_number>/', views.receipt_lookup, name='transaction-receipt-lookup'),
    path('<uuid:transaction_id>/', views.transaction_detail, name='transaction-detail'),
    path('<uuid:transaction_id>/void/', views.void_transaction, name='transaction-void'),
]
# Phase 1 wiring for transactions
