from django.urls import path

from .views import (
    EmployeeProfileDetailView,
    EmployeeProfileListCreateView,
    EmployeeProfileMeView,
)


urlpatterns = [
    path("", EmployeeProfileListCreateView.as_view(), name="employee-profile-list"),
    path("me/", EmployeeProfileMeView.as_view(), name="employee-profile-me"),
    path("<int:profile_id>/", EmployeeProfileDetailView.as_view(), name="employee-profile-detail"),
]
