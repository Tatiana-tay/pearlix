from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from employees.models import EmployeeProfile
from patients.models import Patient
from visits.models import Visit


class Invoice(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"

    visit = models.OneToOneField(
        Visit,
        on_delete=models.PROTECT,
        related_name="invoice",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    doctor_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_invoices",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["doctor_profile", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def clean(self):
        errors = {}

        if self.total_amount is not None and self.total_amount <= Decimal("0"):
            errors["total_amount"] = "Total amount must be positive."

        if self.doctor_profile_id:
            User = get_user_model()
            doctor_user = getattr(self.doctor_profile, "user", None)
            if getattr(doctor_user, "role", None) != User.Role.DOCTOR:
                errors["doctor_profile"] = "Invoice doctor profile must belong to a Doctor."

        if self.visit_id:
            if self.patient_id and self.visit.patient_id != self.patient_id:
                errors["patient"] = "Invoice patient must match the visit patient."
            if (
                self.doctor_profile_id
                and self.visit.doctor_profile_id != self.doctor_profile_id
            ):
                errors["doctor_profile"] = (
                    "Invoice doctor profile must match the visit doctor."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Invoice {self.pk} for {self.patient}"
