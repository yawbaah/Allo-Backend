import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allo_backend.settings')

app = Celery('allo_backend')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Discover tasks.py in all registered applications automatically
app.autodiscover_tasks()