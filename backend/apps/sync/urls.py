from django.urls import path
from . import views

urlpatterns = [
    path('pull/', views.pull, name='sync-pull'),
    path('push/', views.push, name='sync-push'),
]
