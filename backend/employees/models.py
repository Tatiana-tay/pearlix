from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models


class EmployeeProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    specialty = models.CharField(max_length=255, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices)
    phone = models.CharField(max_length=50, blank=True)
    avatar_url = models.URLField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("user__full_name", "id")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["specialty"]),
        ]

    @property
    def role(self) -> str:
        return self.user.role

    def clean(self):
        errors = {}
        User = get_user_model()
        role = getattr(self.user, "role", None)
        specialty = (self.specialty or "").strip()

        if role not in {User.Role.DOCTOR, User.Role.STAFF}:
            errors["user"] = "Employee profile user must have Doctor or Staff role."
        elif role == User.Role.DOCTOR and not specialty:
            errors["specialty"] = "Doctor profiles require a specialty."
        elif role == User.Role.STAFF and specialty:
            errors["specialty"] = "Staff profiles cannot have a specialty."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.specialty = (self.specialty or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.full_name} ({self.user.role})"
