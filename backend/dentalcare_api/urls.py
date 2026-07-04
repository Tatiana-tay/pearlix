from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/employee-profiles/", include("employees.urls")),
    path("api/patients/", include("patients.urls")),
    path("api/", include("ai_results.urls")),
    path("api/", include("attachments.urls")),
    path("api/", include("billing.urls")),
    path("api/", include("visits.urls")),
    path("api/", include("scheduling.urls")),
    path("api/", include("core.urls")),
]
