from django.urls import path
from . import views

urlpatterns = [
    path('mpesa/stk-push/', views.initiate_stk_push, name='mpesa-stk-push'),
    path('mpesa/stk-push/<str:checkout_request_id>/status/', views.stk_status, name='mpesa-stk-status'),
    path('mpesa/callback/', views.stk_callback, name='mpesa-callback'),
    path('mpesa/c2b/confirmation/', views.c2b_confirmation, name='mpesa-c2b-confirmation'),
    path('mpesa/c2b/validation/', views.c2b_validation, name='mpesa-c2b-validation'),
    path('mpesa/transactions/', views.mpesa_transaction_list, name='mpesa-transactions'),
    path('mpesa/reconcile/', views.reconcile, name='mpesa-reconcile'),
]