from django.core.exceptions import ValidationError
from django.db import models

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
