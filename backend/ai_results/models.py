from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from attachments.models import Attachment
from patients.models import Patient
from visits.models import Visit


class AIResult(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PROCESSING = "Processing", "Processing"
        COMPLETED = "Completed", "Completed"
        FAILED = "Failed", "Failed"

    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="ai_results",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="ai_results",
    )
    visit = models.ForeignKey(
        Visit,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ai_results",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    result_summary = models.TextField(blank=True)
    model_name = models.CharField(max_length=255)
    model_version = models.CharField(max_length=100)
    overall_confidence = models.FloatField(null=True, blank=True)
    overlay_url = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_ai_results",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["attachment", "created_at"]),
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["visit", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["model_version", "created_at"]),
        ]

    def clean(self):
        errors = {}

        if self.attachment_id:
            if self.patient_id and self.attachment.patient_id != self.patient_id:
                errors["patient"] = "AI result patient must match the attachment patient."
            if self.visit_id:
                if self.attachment.visit_id:
                    if self.attachment.visit_id != self.visit_id:
                        errors["visit"] = "AI result visit must match the attachment visit."
                elif self.visit.patient_id != self.attachment.patient_id:
                    errors["visit"] = "AI result visit must belong to the attachment patient."

        if self.overall_confidence is not None and not (
            0 <= self.overall_confidence <= 1
        ):
            errors["overall_confidence"] = (
                "Overall confidence must be between 0 and 1."
            )

        if self.metadata is None or not isinstance(self.metadata, dict):
            errors["metadata"] = "Metadata must be a JSON object."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.attachment_id:
            if not self.patient_id:
                self.patient = self.attachment.patient
            if self.visit_id is None:
                self.visit = self.attachment.visit
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"AI result {self.pk} for attachment {self.attachment_id}"


class AIResultFinding(models.Model):
    ADULT_FDI_VALUES = {
        str(quadrant * 10 + tooth)
        for quadrant in (1, 2, 3, 4)
        for tooth in range(1, 9)
    }

    ai_result = models.ForeignKey(
        AIResult,
        on_delete=models.CASCADE,
        related_name="findings",
    )
    tooth_fdi = models.CharField(max_length=2)
    disease_label = models.CharField(max_length=100)
    confidence = models.FloatField()
    bbox = models.JSONField(null=True, blank=True)
    mask = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(fields=["ai_result"]),
            models.Index(fields=["disease_label"]),
            models.Index(fields=["tooth_fdi"]),
        ]

    def clean(self):
        errors = {}

        if self.tooth_fdi not in self.ADULT_FDI_VALUES:
            errors["tooth_fdi"] = "Enter a valid adult FDI tooth number."

        if not (self.disease_label or "").strip():
            errors["disease_label"] = "Disease label is required."

        if self.confidence is None or not (0 <= self.confidence <= 1):
            errors["confidence"] = "Confidence must be between 0 and 1."

        if self.metadata is None or not isinstance(self.metadata, dict):
            errors["metadata"] = "Metadata must be a JSON object."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.disease_label = (self.disease_label or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.disease_label} on tooth {self.tooth_fdi}"
