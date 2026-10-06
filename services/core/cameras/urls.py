from django.urls import path

from . import views

urlpatterns = [
    path("cameras/test", views.CameraTestView.as_view(), name="camera-test"),
    path("cameras", views.CameraListView.as_view(), name="camera-list"),
    path("cameras/<str:camera_id>", views.CameraDetailView.as_view(), name="camera-detail"),
    path(
        "cameras/<str:camera_id>/snapshot",
        views.CameraSnapshotView.as_view(),
        name="camera-snapshot",
    ),
]
