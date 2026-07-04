from django.contrib import admin

from .models import EmployeeProfile


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "role",
        "specialty",
        "updated_at",
    )
    list_filter = ("user__role", "user__status", "gender")
    search_fields = (
        "user__username",
        "user__full_name",
        "user__email",
        "phone",
        "specialty",
    )
    ordering = ("user__full_name", "id")
