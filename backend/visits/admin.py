from django.contrib import admin

from .models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "appointment",
        "patient",
        "doctor_profile",
        "status",
        "started_at",
        "completed_at",
        "updated_at",
    )
    list_filter = ("status",)
    search_fields = (
        "patient__first_name",
        "patient__last_name",
        "doctor_profile__user__full_name",
        "doctor_profile__user__email",
    )
    ordering = ("-started_at", "-id")
    readonly_fields = (
        "appointment",
        "patient",
        "doctor_profile",
        "status",
        "subjective_notes",
        "objective_notes",
        "assessment_notes",
        "plan_notes",
        "general_notes",
        "started_at",
        "completed_at",
        "version",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
