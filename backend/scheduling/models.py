from datetime import timezone as datetime_timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from employees.models import EmployeeProfile


class WorkingShift(models.Model):
    class DayOfWeek(models.TextChoices):
        MONDAY = "Monday", "Monday"
        TUESDAY = "Tuesday", "Tuesday"
        WEDNESDAY = "Wednesday", "Wednesday"
        THURSDAY = "Thursday", "Thursday"
        FRIDAY = "Friday", "Friday"
        SATURDAY = "Saturday", "Saturday"
        SUNDAY = "Sunday", "Sunday"

    employee_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="working_shifts",
    )
    day_of_week = models.CharField(max_length=9, choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("employee_profile__user__full_name", "day_of_week", "start_time", "id")
        indexes = [
            models.Index(fields=["employee_profile", "day_of_week"]),
            models.Index(fields=["employee_profile", "day_of_week", "is_active"]),
        ]

    def clean(self):
        errors = {}

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            errors["end_time"] = "End time must be after start time."

        if (
            self.is_active
            and self.employee_profile_id
            and self.day_of_week
            and self.start_time
            and self.end_time
            and "end_time" not in errors
        ):
            overlapping = WorkingShift.objects.filter(
                employee_profile_id=self.employee_profile_id,
                day_of_week=self.day_of_week,
                is_active=True,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                errors["start_time"] = (
                    "Active working shifts cannot overlap for the same employee and day."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.employee_profile.user.full_name} "
            f"{self.day_of_week} {self.start_time}-{self.end_time}"
        )


class AvailabilityException(models.Model):
    class Reason(models.TextChoices):
        LEAVE = "Leave", "Leave"
        SICK_LEAVE = "Sick Leave", "Sick Leave"
        PERSONAL = "Personal", "Personal"
        TRAINING = "Training", "Training"
        EMERGENCY = "Emergency", "Emergency"
        OTHER = "Other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        CANCELLED = "Cancelled", "Cancelled"

    employee_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="availability_exceptions",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_availability_exceptions",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_availability_exceptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("employee_profile__user__full_name", "start_at", "id")
        indexes = [
            models.Index(fields=["employee_profile", "status", "start_at", "end_at"]),
            models.Index(fields=["start_at"]),
            models.Index(fields=["end_at"]),
        ]

    def clean(self):
        errors = {}

        if self.start_at and timezone.is_naive(self.start_at):
            errors["start_at"] = "Start datetime must include a timezone."
        if self.end_at and timezone.is_naive(self.end_at):
            errors["end_at"] = "End datetime must include a timezone."

        if self.start_at and self.end_at and "start_at" not in errors and "end_at" not in errors:
            if self.start_at >= self.end_at:
                errors["end_at"] = "End datetime must be after start datetime."

        if (
            self.status == self.Status.ACTIVE
            and self.employee_profile_id
            and self.start_at
            and self.end_at
            and "start_at" not in errors
            and "end_at" not in errors
        ):
            overlapping = AvailabilityException.objects.filter(
                employee_profile_id=self.employee_profile_id,
                status=self.Status.ACTIVE,
                start_at__lt=self.end_at,
                end_at__gt=self.start_at,
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                errors["start_at"] = (
                    "Active availability exceptions cannot overlap for the same employee."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.start_at and not timezone.is_naive(self.start_at):
            self.start_at = self.start_at.astimezone(datetime_timezone.utc)
        if self.end_at and not timezone.is_naive(self.end_at):
            self.end_at = self.end_at.astimezone(datetime_timezone.utc)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.employee_profile.user.full_name} "
            f"{self.start_at}-{self.end_at} ({self.status})"
        )
