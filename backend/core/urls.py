from django.urls import path

from .views import ClinicSettingsView, health


urlpatterns = [
    path("health/", health, name="health"),
    path("clinic/settings/", ClinicSettingsView.as_view(), name="clinic-settings"),
]
