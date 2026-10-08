from django.urls import path

from . import internal

urlpatterns = [
    path("config", internal.config, name="internal-config"),
    path("events", internal.report, name="internal-events"),
]
