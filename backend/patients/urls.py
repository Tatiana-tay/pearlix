from django.urls import path

from .views import PatientDetailView, PatientListCreateView


urlpatterns = [
    path("", PatientListCreateView.as_view(), name="patient-list"),
    path("<int:patient_id>/", PatientDetailView.as_view(), name="patient-detail"),
]
