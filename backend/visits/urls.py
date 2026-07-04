from django.urls import path

from .views import (
    VisitActiveView,
    VisitCompleteView,
    VisitDetailView,
    VisitListView,
    VisitStartView,
)


urlpatterns = [
    path("appointments/<int:appointment_id>/start-visit/", VisitStartView.as_view(), name="appointment-start-visit"),
    path("visits/", VisitListView.as_view(), name="visit-list"),
    path("visits/start/", VisitStartView.as_view(), name="visit-start"),
    path("visits/active/", VisitActiveView.as_view(), name="visit-active"),
    path("visits/<int:visit_id>/", VisitDetailView.as_view(), name="visit-detail"),
    path("visits/<int:visit_id>/notes/", VisitDetailView.as_view(), name="visit-notes"),
    path("visits/<int:visit_id>/complete/", VisitCompleteView.as_view(), name="visit-complete"),
]
