from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from patients.models import Patient
from visits.models import Visit


def attachment_upload_path(instance, filename):
    today = timezone.now()
    return (
        f"attachments/patient_{instance.patient_id}/"
        f"{today:%Y/%m/%d}/{filename}"
    )


class Attachment(models.Model):
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS_BY_CONTENT_TYPE = {
        "image/jpeg": {".jpg", ".jpeg"},
        "image/png": {".png"},
        "image/webp": {".webp"},
        "application/pdf": {".pdf"},
        "application/dicom": {".dcm", ".dicom"},
        "application/octet-stream": {".dcm", ".dicom"},
    }
    BLOCKED_EXTENSIONS = {
        ".7z",
        ".bat",
        ".cmd",
        ".dll",
        ".exe",
        ".gz",
        ".js",
        ".msi",
        ".ps1",
        ".rar",
        ".sh",
        ".tar",
        ".vbs",
        ".zip",
    }

    class AttachmentType(models.TextChoices):
        XRAY = "X-ray", "X-ray"
        DOCUMENT = "Document", "Document"
        OTHER = "Other", "Other"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    visit = models.ForeignKey(
        Visit,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_attachments",
    )
    file = models.FileField(upload_to=attachment_upload_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    attachment_type = models.CharField(
        max_length=20,
        choices=AttachmentType.choices,
        default=AttachmentType.XRAY,
    )
    description = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["visit", "created_at"]),
            models.Index(fields=["uploaded_by", "created_at"]),
            models.Index(fields=["attachment_type", "created_at"]),
            models.Index(fields=["is_deleted", "created_at"]),
        ]

    @classmethod
    def normalized_content_type(cls, content_type):
        return (content_type or "").split(";")[0].strip().lower()

    @classmethod
    def validate_file_metadata(cls, *, original_filename, content_type, size_bytes):
        errors = {}
        normalized_type = cls.normalized_content_type(content_type)
        extension = Path(original_filename or "").suffix.lower()

        if not original_filename:
            errors["original_filename"] = "Original filename is required."
        if extension in cls.BLOCKED_EXTENSIONS:
            errors["original_filename"] = "This file extension is not supported."
        if not normalized_type:
            errors["content_type"] = "Content type is required."
        elif normalized_type not in cls.ALLOWED_EXTENSIONS_BY_CONTENT_TYPE:
            errors["content_type"] = "Unsupported file type."
        elif extension not in cls.ALLOWED_EXTENSIONS_BY_CONTENT_TYPE[normalized_type]:
            errors["original_filename"] = (
                "File extension does not match the uploaded content type."
            )

        if size_bytes is None:
            errors["size_bytes"] = "File size is required."
        elif size_bytes > cls.MAX_FILE_SIZE_BYTES:
            errors["size_bytes"] = "File size cannot exceed 10 MB."
        elif size_bytes <= 0:
            errors["size_bytes"] = "File cannot be empty."

        if errors:
            raise ValidationError(errors)

    def clean(self):
        errors = {}

        if self.visit_id and self.patient_id and self.visit.patient_id != self.patient_id:
            errors["visit"] = "Attachment visit must belong to the selected patient."

        try:
            self.validate_file_metadata(
                original_filename=self.original_filename,
                content_type=self.content_type,
                size_bytes=self.size_bytes,
            )
        except ValidationError as exc:
            errors.update(exc.message_dict)

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.content_type = self.normalized_content_type(self.content_type)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.original_filename or f"Attachment {self.pk}"
