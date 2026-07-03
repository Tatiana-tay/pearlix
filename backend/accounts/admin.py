from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class DentalCareUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "full_name",
        "role",
        "status",
        "must_change_password",
        "is_staff",
        "is_superuser",
    )
    list_filter = ("role", "status", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "full_name")
    ordering = ("username",)

    fieldsets = UserAdmin.fieldsets + (
        (
            "DentalCare",
            {
                "fields": (
                    "full_name",
                    "role",
                    "status",
                    "must_change_password",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "DentalCare",
            {
                "fields": (
                    "email",
                    "full_name",
                    "role",
                    "status",
                    "must_change_password",
                )
            },
        ),
    )
