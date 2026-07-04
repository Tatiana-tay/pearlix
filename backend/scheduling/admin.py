from django.contrib import admin

from .models import WorkingShift


@admin.register(WorkingShift)
class WorkingShiftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee_profile",
        "day_of_week",
        "start_time",
        "end_time",
        "is_active",
        "updated_at",
    )
    list_filter = ("day_of_week", "is_active", "employee_profile__user__role")
    search_fields = (
        "employee_profile__user__username",
        "employee_profile__user__full_name",
        "employee_profile__user__email",
    )
    ordering = ("employee_profile__user__full_name", "day_of_week", "start_time")
