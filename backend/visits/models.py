from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from employees.models import EmployeeProfile
from patients.models import Patient
from scheduling.models import Appointment


class Visit(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        COMPLETED = "Completed", "Completed"

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,
        related_name="visit",
    )
    doctor_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="visits",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="visits",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    subjective_notes = models.TextField(blank=True)
    objective_notes = models.TextField(blank=True)
    assessment_notes = models.TextField(blank=True)
    plan_notes = models.TextField(blank=True)
    general_notes = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-started_at", "-id")
        indexes = [
            models.Index(fields=["doctor_profile", "status"]),
            models.Index(fields=["patient"]),
            models.Index(fields=["appointment"]),
            models.Index(fields=["started_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor_profile"],
                condition=Q(status="Active"),
                name="one_active_visit_per_doctor",
            )
        ]

    def clean(self):
        errors = {}

        if self.doctor_profile_id:
            User = get_user_model()
            doctor_user = getattr(self.doctor_profile, "user", None)
            if getattr(doctor_user, "role", None) != User.Role.DOCTOR:
                errors["doctor_profile"] = "Visit doctor profile must belong to a Doctor."

        if self.appointment_id:
            if self.patient_id and self.appointment.patient_id != self.patient_id:
                errors["patient"] = "Visit patient must match the appointment patient."
            if (
                self.doctor_profile_id
                and self.appointment.doctor_profile_id != self.doctor_profile_id
            ):
                errors["doctor_profile"] = (
                    "Visit doctor profile must match the appointment doctor."
                )

        if self.status == self.Status.ACTIVE and self.completed_at is not None:
            errors["completed_at"] = "Active visits cannot have a completed timestamp."
        if self.status == self.Status.COMPLETED and self.completed_at is None:
            errors["completed_at"] = "Completed visits require a completed timestamp."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Visit {self.pk} for {self.patient}"
