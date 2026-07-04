from datetime import timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import ClinicSettings
from employees.models import EmployeeProfile
from patients.models import Patient


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


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "Scheduled", "Scheduled"
        ARRIVED = "Arrived", "Arrived"
        CHECKED_IN = "Checked-in", "Checked-in"
        IN_VISIT = "In Visit", "In Visit"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"
        NO_SHOW = "No-show", "No-show"
        POSTPONED = "Postponed", "Postponed"
        NEEDS_RESCHEDULE = "Needs Reschedule", "Needs Reschedule"

    class VisitType(models.TextChoices):
        INITIAL_CONSULTATION = "Initial Consultation", "Initial Consultation"
        ROUTINE_CHECKUP = "Routine Checkup", "Routine Checkup"
        TREATMENT_CONTINUATION = "Treatment Continuation", "Treatment Continuation"
        FOLLOW_UP_VISIT = "Follow-up Visit", "Follow-up Visit"
        EMERGENCY_VISIT = "Emergency Visit", "Emergency Visit"
        X_RAY_REVIEW = "X-ray Review", "X-ray Review"
        POST_TREATMENT_REVIEW = "Post-treatment Review", "Post-treatment Review"
        CLEANING_VISIT = "Cleaning Visit", "Cleaning Visit"

    BLOCKING_STATUSES = (
        Status.SCHEDULED,
        Status.ARRIVED,
        Status.CHECKED_IN,
        Status.IN_VISIT,
        Status.NEEDS_RESCHEDULE,
    )
    MIN_DURATION_MINUTES = 15

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    doctor_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    visit_type = models.CharField(max_length=40, choices=VisitType.choices)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_appointments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("start_at", "id")
        indexes = [
            models.Index(fields=["doctor_profile", "start_at", "end_at"]),
            models.Index(fields=["status", "start_at"]),
            models.Index(fields=["patient", "start_at"]),
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

        if self.duration_minutes is not None:
            if self.duration_minutes < self.MIN_DURATION_MINUTES:
                errors["duration_minutes"] = (
                    f"Duration must be at least {self.MIN_DURATION_MINUTES} minutes."
                )

        if (
            self.start_at
            and self.end_at
            and self.duration_minutes is not None
            and "start_at" not in errors
            and "end_at" not in errors
            and "duration_minutes" not in errors
        ):
            interval_minutes = int((self.end_at - self.start_at).total_seconds() // 60)
            if self.end_at - self.start_at != timedelta(minutes=interval_minutes):
                errors["duration_minutes"] = "Appointment interval must be whole minutes."
            elif interval_minutes != self.duration_minutes:
                errors["duration_minutes"] = (
                    "Duration minutes must match start and end datetime interval."
                )

        if self.doctor_profile_id:
            User = get_user_model()
            doctor_user = getattr(self.doctor_profile, "user", None)
            if getattr(doctor_user, "role", None) != User.Role.DOCTOR:
                errors["doctor_profile"] = "Appointment doctor profile must belong to a Doctor."
            elif (
                not getattr(doctor_user, "is_active", False)
                or getattr(doctor_user, "status", None) != User.Status.ACTIVE
            ):
                errors["doctor_profile"] = "Appointment doctor must be active."

        if not errors and self._has_scheduling_fields():
            errors.update(self._validate_scheduling_rules())

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.start_at and not timezone.is_naive(self.start_at):
            self.start_at = self.start_at.astimezone(datetime_timezone.utc)
        if self.end_at and not timezone.is_naive(self.end_at):
            self.end_at = self.end_at.astimezone(datetime_timezone.utc)
        self.full_clean()
        return super().save(*args, **kwargs)

    def _has_scheduling_fields(self):
        return (
            self.patient_id
            and self.doctor_profile_id
            and self.start_at
            and self.end_at
            and self.duration_minutes is not None
        )

    def _validate_scheduling_rules(self):
        errors = {}

        if self.status in self.BLOCKING_STATUSES and self._has_same_doctor_overlap():
            errors["start_at"] = "Doctor already has an overlapping appointment."
            return errors

        if not self._is_inside_active_working_shift():
            errors["start_at"] = "Appointment must be inside an active doctor working shift."
            return errors

        if self._overlaps_active_leave():
            errors["start_at"] = "Appointment overlaps active doctor leave."
            return errors

        if self.status in self.BLOCKING_STATUSES and self._exceeds_clinic_capacity():
            errors["start_at"] = "Clinic appointment capacity exceeded."

        return errors

    def _base_overlapping_appointments(self):
        queryset = Appointment.objects.filter(
            status__in=self.BLOCKING_STATUSES,
            start_at__lt=self.end_at,
            end_at__gt=self.start_at,
        )
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        return queryset

    def _has_same_doctor_overlap(self):
        return self._base_overlapping_appointments().filter(
            doctor_profile_id=self.doctor_profile_id,
        ).exists()

    def _is_inside_active_working_shift(self):
        settings = ClinicSettings.get_solo()
        clinic_tz = ZoneInfo(settings.clinic_timezone)
        local_start = self.start_at.astimezone(clinic_tz)
        local_end = self.end_at.astimezone(clinic_tz)
        if local_start.date() != local_end.date():
            return False

        day_of_week = WorkingShift.DayOfWeek(local_start.strftime("%A"))
        return WorkingShift.objects.filter(
            employee_profile_id=self.doctor_profile_id,
            day_of_week=day_of_week,
            is_active=True,
            start_time__lte=local_start.time(),
            end_time__gte=local_end.time(),
        ).exists()

    def _overlaps_active_leave(self):
        return AvailabilityException.objects.filter(
            employee_profile_id=self.doctor_profile_id,
            status=AvailabilityException.Status.ACTIVE,
            start_at__lt=self.end_at,
            end_at__gt=self.start_at,
        ).exists()

    def _exceeds_clinic_capacity(self):
        settings = ClinicSettings.get_solo()
        return self._base_overlapping_appointments().count() >= (
            settings.max_simultaneous_appointments
        )

    def __str__(self) -> str:
        return f"{self.patient.full_name} with {self.doctor_profile.user.full_name}"
