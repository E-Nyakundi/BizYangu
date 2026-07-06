"""
BizYangu Celery configuration.
"""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bizyangu.settings.development')

app = Celery('bizyangu')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
