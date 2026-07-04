from django.urls import path

from .views import WorkingShiftDetailView, WorkingShiftListCreateView


urlpatterns = [
    path("", WorkingShiftListCreateView.as_view(), name="working-shift-list"),
    path("<int:shift_id>/", WorkingShiftDetailView.as_view(), name="working-shift-detail"),
]
