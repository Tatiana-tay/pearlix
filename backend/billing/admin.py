from django.contrib import admin

from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "visit",
        "patient",
        "doctor_profile",
        "total_amount",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status",)
    search_fields = (
        "patient__first_name",
        "patient__last_name",
        "doctor_profile__user__full_name",
        "doctor_profile__user__email",
    )
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "visit",
        "patient",
        "doctor_profile",
        "created_by",
        "total_amount",
        "status",
        "note",
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
