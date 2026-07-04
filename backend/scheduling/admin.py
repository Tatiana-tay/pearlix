from django.contrib import admin

from .models import Appointment, AppointmentChangeLog, AvailabilityException, WorkingShift


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


@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee_profile",
        "start_at",
        "end_at",
        "status",
        "updated_at",
    )
    list_filter = ("status", "reason", "employee_profile__user__role")
    search_fields = (
        "employee_profile__user__username",
        "employee_profile__user__full_name",
        "employee_profile__user__email",
    )
    ordering = ("employee_profile__user__full_name", "start_at")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "doctor_profile",
        "start_at",
        "end_at",
        "status",
        "updated_at",
    )
    list_filter = ("status", "visit_type", "doctor_profile__user__role")
    search_fields = (
        "patient__first_name",
        "patient__last_name",
        "doctor_profile__user__full_name",
        "doctor_profile__user__email",
    )
    ordering = ("start_at", "id")


@admin.register(AppointmentChangeLog)
class AppointmentChangeLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "appointment",
        "action",
        "previous_status",
        "new_status",
        "changed_by",
        "created_at",
    )
    list_filter = ("action", "previous_status", "new_status")
    search_fields = (
        "appointment__patient__first_name",
        "appointment__patient__last_name",
        "appointment__doctor_profile__user__full_name",
        "changed_by__email",
    )
    ordering = ("created_at", "id")
    readonly_fields = (
        "appointment",
        "action",
        "previous_status",
        "new_status",
        "old_doctor_profile",
        "new_doctor_profile",
        "old_start_at",
        "old_end_at",
        "new_start_at",
        "new_end_at",
        "changed_by",
        "reason",
        "note",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
