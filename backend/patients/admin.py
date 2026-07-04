from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "gender",
        "phone_number",
        "email",
        "national_id_or_passport",
        "updated_at",
    )
    list_filter = ("gender", "blood_group")
    search_fields = (
        "first_name",
        "last_name",
        "phone_number",
        "email",
        "national_id_or_passport",
    )
    ordering = ("-updated_at", "-id")
