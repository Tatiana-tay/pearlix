from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import models


class ClinicSettings(models.Model):
    DEFAULT_TIMEZONE = "Asia/Damascus"
    DEFAULT_MAX_SIMULTANEOUS_APPOINTMENTS = 1
    SINGLETON_PK = 1

    clinic_timezone = models.CharField(max_length=100, default=DEFAULT_TIMEZONE)
    max_simultaneous_appointments = models.PositiveIntegerField(
        default=DEFAULT_MAX_SIMULTANEOUS_APPOINTMENTS
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Clinic settings"
        verbose_name_plural = "Clinic settings"

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return settings

    def clean(self):
        errors = {}

        try:
            ZoneInfo(self.clinic_timezone)
        except ZoneInfoNotFoundError:
            errors["clinic_timezone"] = "Enter a valid IANA timezone name."

        if self.max_simultaneous_appointments < 1:
            errors["max_simultaneous_appointments"] = (
                "Max simultaneous appointments must be at least 1."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return "Clinic settings"
