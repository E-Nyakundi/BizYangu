from django.urls import path
from . import views

urlpatterns = [
    path('mpesa/stk-push/', views.initiate_stk_push, name='mpesa-stk-push'),
    path('mpesa/stk-push/<str:checkout_request_id>/status/', views.stk_status, name='mpesa-stk-status'),
    path('mpesa/callback/', views.stk_callback, name='mpesa-callback'),
    path('mpesa/c2b/confirmation/', views.c2b_confirmation, name='mpesa-c2b-confirmation'),
    path('mpesa/c2b/validation/', views.c2b_validation, name='mpesa-c2b-validation'),
    path('mpesa/sms-confirmation/', views.sms_confirmation, name='mpesa-sms-confirmation'),
    path('mpesa/transactions/', views.mpesa_transaction_list, name='mpesa-transactions'),
    path('mpesa/reconcile/', views.reconcile, name='mpesa-reconcile'),

    # Subscription billing (company shortcode — business paying BizYangu)
    path('mpesa/subscription/stk-push/', views.initiate_subscription_payment, name='mpesa-subscription-stk-push'),
    path(
        'mpesa/subscription/stk-push/<str:checkout_request_id>/status/',
        views.subscription_payment_status, name='mpesa-subscription-stk-status',
    ),
    path('mpesa/subscription/callback/', views.subscription_callback, name='mpesa-subscription-callback'),

    # Per-business M-Pesa credentials (owner's own till/paybill)
    path('mpesa/business-credentials/', views.business_mpesa_credentials, name='mpesa-business-credentials'),
    path(
        'mpesa/business-credentials/verify/',
        views.verify_business_mpesa_credentials, name='mpesa-business-credentials-verify',
    ),
    path(
        'mpesa/business-credentials/deactivate/',
        views.deactivate_business_mpesa_credentials, name='mpesa-business-credentials-deactivate',
    ),
]