from django.urls import path

from .views import (
    AIResultDetailView,
    AIResultFindingListView,
    AIResultListCreateView,
    AttachmentLatestAIResultView,
)


urlpatterns = [
    path("ai-results/", AIResultListCreateView.as_view(), name="ai-result-list"),
    path(
        "ai-results/<int:ai_result_id>/",
        AIResultDetailView.as_view(),
        name="ai-result-detail",
    ),
    path(
        "ai-results/<int:ai_result_id>/findings/",
        AIResultFindingListView.as_view(),
        name="ai-result-findings",
    ),
    path(
        "attachments/<int:attachment_id>/ai-results/",
        AIResultListCreateView.as_view(),
        name="attachment-ai-results",
    ),
    path(
        "attachments/<int:attachment_id>/ai-result/",
        AttachmentLatestAIResultView.as_view(),
        name="attachment-latest-ai-result",
    ),
]
