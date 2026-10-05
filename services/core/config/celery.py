import os

from celery import Celery
from django.conf import settings
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("cammind")
app.config_from_object("django.conf:settings", namespace="CELERY")
# Explicit exchange + routing key per queue, so each stage's tasks reach only its workers.
app.conf.task_queues = tuple(Queue(q, Exchange(q), routing_key=q) for q in settings.CELERY_QUEUES)
app.autodiscover_tasks()
