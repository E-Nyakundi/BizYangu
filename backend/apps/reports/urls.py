from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='reports-dashboard'),
    path('daily/', views.daily_report, name='reports-daily'),
    path('period/', views.period_report, name='reports-period'),
    path('growth/', views.growth_report, name='reports-growth'),
    path('products/', views.product_performance_report, name='reports-products'),
    path('losses/', views.loss_report, name='reports-losses'),
    path('eod-summary/', views.eod_summary, name='reports-eod-summary'),
    path('data-health/', views.data_health, name='reports-data-health'),
    path('milestones/', views.milestones, name='reports-milestones'),
]