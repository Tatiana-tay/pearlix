from django.urls import path

from .views import (
    AttachmentDetailView,
    AttachmentListCreateView,
    AttachmentOriginalUrlView,
)


urlpatterns = [
    path("attachments/", AttachmentListCreateView.as_view(), name="attachment-list"),
    path(
        "attachments/<int:attachment_id>/",
        AttachmentDetailView.as_view(),
        name="attachment-detail",
    ),
    path(
        "attachments/<int:attachment_id>/original-url/",
        AttachmentOriginalUrlView.as_view(),
        name="attachment-original-url",
    ),
    path(
        "visits/<int:visit_id>/attachments/",
        AttachmentListCreateView.as_view(),
        name="visit-attachments",
    ),
]
