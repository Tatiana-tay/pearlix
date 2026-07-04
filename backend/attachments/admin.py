from django.contrib import admin

from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "visit",
        "attachment_type",
        "original_filename",
        "content_type",
        "size_bytes",
        "uploaded_by",
        "is_deleted",
        "created_at",
    )
    list_filter = ("attachment_type", "content_type", "is_deleted")
    search_fields = (
        "patient__first_name",
        "patient__last_name",
        "original_filename",
        "uploaded_by__full_name",
        "uploaded_by__email",
    )
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "patient",
        "visit",
        "uploaded_by",
        "file",
        "original_filename",
        "content_type",
        "size_bytes",
        "attachment_type",
        "description",
        "is_deleted",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
