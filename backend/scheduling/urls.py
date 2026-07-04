from django.urls import path

from .views import (
    AppointmentDetailView,
    AppointmentListCreateView,
    AvailabilityExceptionDetailView,
    AvailabilityExceptionListCreateView,
    WorkingShiftDetailView,
    WorkingShiftListCreateView,
)


urlpatterns = [
    path("appointments/", AppointmentListCreateView.as_view(), name="appointment-list"),
    path(
        "appointments/<int:appointment_id>/",
        AppointmentDetailView.as_view(),
        name="appointment-detail",
    ),
    path("working-shifts/", WorkingShiftListCreateView.as_view(), name="working-shift-list"),
    path(
        "working-shifts/<int:shift_id>/",
        WorkingShiftDetailView.as_view(),
        name="working-shift-detail",
    ),
    path(
        "availability-exceptions/",
        AvailabilityExceptionListCreateView.as_view(),
        name="availability-exception-list",
    ),
    path(
        "availability-exceptions/<int:exception_id>/",
        AvailabilityExceptionDetailView.as_view(),
        name="availability-exception-detail",
    ),
    path(
        "leave-exceptions/",
        AvailabilityExceptionListCreateView.as_view(),
        name="leave-exception-list",
    ),
    path(
        "leave-exceptions/<int:exception_id>/",
        AvailabilityExceptionDetailView.as_view(),
        name="leave-exception-detail",
    ),
]
