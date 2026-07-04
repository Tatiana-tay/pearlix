from django.contrib import admin

from .models import AIResult, AIResultFinding


@admin.register(AIResult)
class AIResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attachment",
        "patient",
        "visit",
        "status",
        "model_name",
        "model_version",
        "overall_confidence",
        "created_at",
    )
    list_filter = ("status", "model_version")
    search_fields = (
        "attachment__original_filename",
        "patient__first_name",
        "patient__last_name",
        "model_name",
        "model_version",
    )
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "attachment",
        "patient",
        "visit",
        "status",
        "result_summary",
        "model_name",
        "model_version",
        "overall_confidence",
        "overlay_url",
        "error_message",
        "metadata",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AIResultFinding)
class AIResultFindingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ai_result",
        "tooth_fdi",
        "disease_label",
        "confidence",
        "created_at",
    )
    list_filter = ("disease_label",)
    search_fields = (
        "ai_result__attachment__original_filename",
        "disease_label",
        "tooth_fdi",
    )
    ordering = ("id",)
    readonly_fields = (
        "ai_result",
        "tooth_fdi",
        "disease_label",
        "confidence",
        "bbox",
        "mask",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
