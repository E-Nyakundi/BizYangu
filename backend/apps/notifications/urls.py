from django.urls import path
from . import views

urlpatterns = [
    path('devices/', views.register_device, name='device-register'),
    path('devices/unregister/', views.unregister_device, name='device-unregister'),
    path('log/', views.notification_log, name='notification-log'),
]
