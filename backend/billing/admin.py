from django.contrib import admin

from .models import Invoice, InvoiceAuditLog, Payment


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


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "amount",
        "method",
        "received_by",
        "created_at",
    )
    list_filter = ("method",)
    search_fields = (
        "invoice__patient__first_name",
        "invoice__patient__last_name",
        "received_by__full_name",
        "received_by__email",
    )
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "invoice",
        "amount",
        "method",
        "received_by",
        "note",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InvoiceAuditLog)
class InvoiceAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "action",
        "previous_total",
        "new_total",
        "previous_status",
        "new_status",
        "changed_by",
        "created_at",
    )
    list_filter = ("action",)
    search_fields = (
        "invoice__patient__first_name",
        "invoice__patient__last_name",
        "changed_by__full_name",
        "changed_by__email",
    )
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "invoice",
        "action",
        "previous_total",
        "new_total",
        "previous_status",
        "new_status",
        "changed_by",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
