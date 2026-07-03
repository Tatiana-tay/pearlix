from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.checks import run_checks
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ClinicSettings


class HealthEndpointTests(APITestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/api/health/", HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class SettingsTests(TestCase):
    def test_settings_import_and_checks_work(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(run_checks(), [])


class ClinicSettingsModelTests(TestCase):
    def test_default_singleton_settings_can_be_retrieved_or_created(self):
        settings_row = ClinicSettings.get_solo()

        self.assertEqual(settings_row.pk, ClinicSettings.SINGLETON_PK)
        self.assertEqual(settings_row.clinic_timezone, "Asia/Damascus")
        self.assertEqual(settings_row.max_simultaneous_appointments, 1)

    def test_valid_iana_timezone_is_accepted(self):
        settings_row = ClinicSettings.get_solo()
        settings_row.clinic_timezone = "Europe/Brussels"

        settings_row.full_clean()
        settings_row.save()

        settings_row.refresh_from_db()
        self.assertEqual(settings_row.clinic_timezone, "Europe/Brussels")

    def test_invalid_timezone_is_rejected(self):
        settings_row = ClinicSettings.get_solo()
        settings_row.clinic_timezone = "UTC+03:00"

        with self.assertRaises(ValidationError):
            settings_row.full_clean()

    def test_max_simultaneous_appointments_must_be_at_least_one(self):
        settings_row = ClinicSettings.get_solo()
        settings_row.max_simultaneous_appointments = 0

        with self.assertRaises(ValidationError):
            settings_row.full_clean()

    def test_singleton_behavior_avoids_multiple_settings_rows(self):
        first = ClinicSettings.get_solo()
        second = ClinicSettings.get_solo()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ClinicSettings.objects.count(), 1)


class ClinicSettingsAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = User.objects.create_user(
            username="admin-settings@example.com",
            email="admin-settings@example.com",
            password="test-pass-123",
            full_name="Admin Settings",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.staff = User.objects.create_user(
            username="staff-settings@example.com",
            email="staff-settings@example.com",
            password="test-pass-123",
            full_name="Staff Settings",
            role=User.Role.STAFF,
            status=User.Status.ACTIVE,
        )
        self.doctor = User.objects.create_user(
            username="doctor-settings@example.com",
            email="doctor-settings@example.com",
            password="test-pass-123",
            full_name="Doctor Settings",
            role=User.Role.DOCTOR,
            status=User.Status.ACTIVE,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_unauthenticated_get_clinic_settings_is_rejected(self):
        response = self.client.get("/api/clinic/settings/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_admin_can_get_settings(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/clinic/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["clinicTimezone"], "Asia/Damascus")
        self.assertEqual(response.data["maxSimultaneousAppointments"], 1)

    def test_authenticated_staff_can_get_settings(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/clinic/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_doctor_can_get_settings(self):
        self.authenticate(self.doctor)

        response = self.client.get("/api/clinic/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_patch_clinic_timezone(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            "/api/clinic/settings/",
            {"clinicTimezone": "Europe/Brussels"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["clinicTimezone"], "Europe/Brussels")

    def test_admin_can_patch_max_simultaneous_appointments(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            "/api/clinic/settings/",
            {"maxSimultaneousAppointments": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["maxSimultaneousAppointments"], 2)

    def test_staff_cannot_patch_clinic_settings(self):
        self.authenticate(self.staff)

        response = self.client.patch(
            "/api/clinic/settings/",
            {"clinicTimezone": "Europe/Brussels"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_patch_clinic_settings(self):
        self.authenticate(self.doctor)

        response = self.client.patch(
            "/api/clinic/settings/",
            {"clinicTimezone": "Europe/Brussels"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_timezone_patch_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            "/api/clinic/settings/",
            {"clinicTimezone": "UTC+03:00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_capacity_patch_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            "/api/clinic/settings/",
            {"maxSimultaneousAppointments": 0},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_clinic_settings_response_uses_camel_case_fields(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/clinic/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("clinicTimezone", response.data)
        self.assertIn("maxSimultaneousAppointments", response.data)
        self.assertIn("updatedAt", response.data)
        self.assertNotIn("clinic_timezone", response.data)

    def test_health_endpoint_remains_public(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_auth_me_still_works(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "admin-settings@example.com")

    def test_auth_roles_still_works(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/auth/roles/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"roles": ["Admin", "Staff", "Doctor"]})
