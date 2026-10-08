from django.urls import path

from . import views

urlpatterns = [
    path("events", views.EventListView.as_view(), name="event-list"),
    path("events/<str:event_id>", views.EventDetailView.as_view(), name="event-detail"),
    path(
        "events/<str:event_id>/<str:kind>.jpg", views.EventImageView.as_view(), name="event-image"
    ),
]
