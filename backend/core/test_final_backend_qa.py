from io import StringIO

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from billing.models import Invoice, Payment
from scheduling.test_appointments import AppointmentTestHelpers


class FinalBackendQASmokeTests(AppointmentTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=3)
        User = get_user_model()
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.staff = self.make_user(User.Role.STAFF, "staff-final-qa@example.com")
        self.inactive = self.make_user(
            User.Role.STAFF,
            "inactive-final-qa@example.com",
            user_status=User.Status.INACTIVE,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_health_auth_roles_and_settings_entry_points_are_available(self):
        health_response = self.client.get("/api/health/")
        anonymous_roles_response = self.client.get("/api/auth/roles/")

        self.authenticate(self.staff)
        roles_response = self.client.get("/api/auth/roles/")
        me_response = self.client.get("/api/auth/me/")
        settings_response = self.client.get("/api/clinic/settings/")

        self.authenticate(self.inactive)
        inactive_me_response = self.client.get("/api/auth/me/")

        self.assertEqual(health_response.status_code, status.HTTP_200_OK)
        self.assertEqual(health_response.data, {"status": "ok"})
        self.assertEqual(anonymous_roles_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(roles_response.status_code, status.HTTP_200_OK)
        self.assertEqual(roles_response.data, {"roles": ["Admin", "Staff", "Doctor"]})
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["role"], "Staff")
        self.assertIn("mustChangePassword", me_response.data)
        self.assertEqual(settings_response.status_code, status.HTTP_200_OK)
        self.assertIn("clinicTimezone", settings_response.data)
        self.assertIn("maxSimultaneousAppointments", settings_response.data)
        self.assertIn(
            inactive_me_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_dev_seed_command_is_idempotent_and_uses_documented_users(self):
        first_output = StringIO()
        second_output = StringIO()

        call_command("seed_dev_users", stdout=first_output)
        call_command("seed_dev_users", stdout=second_output)

        User = get_user_model()
        expected = {
            "admin@example.com": (User.Role.ADMIN, User.Status.ACTIVE, True, "Admin123!"),
            "staff@example.com": (User.Role.STAFF, User.Status.ACTIVE, True, "Staff123!"),
            "doctor@example.com": (User.Role.DOCTOR, User.Status.ACTIVE, True, "Doctor123!"),
            "inactive@example.com": (
                User.Role.STAFF,
                User.Status.INACTIVE,
                False,
                "Inactive123!",
            ),
        }
        for email, (role, user_status, is_active, password) in expected.items():
            user = User.objects.get(email=email)
            self.assertEqual(user.username, email)
            self.assertEqual(user.role, role)
            self.assertEqual(user.status, user_status)
            self.assertEqual(user.is_active, is_active)
            self.assertTrue(user.check_password(password))

        self.assertIn("created", first_output.getvalue())
        self.assertIn("updated", second_output.getvalue())

    def test_final_backend_surface_omits_out_of_scope_models_and_routes(self):
        model_names_by_app = {
            app_label: set(model_map)
            for app_label, model_map in apps.all_models.items()
            if app_label
            in {
                "accounts",
                "core",
                "patients",
                "employees",
                "scheduling",
                "visits",
                "billing",
                "attachments",
                "ai_results",
            }
        }

        self.assertEqual(
            model_names_by_app["billing"],
            {"invoice", "invoiceauditlog", "payment"},
        )
        for forbidden_model in (
            "service",
            "servicecatalog",
            "invoiceitem",
            "rolepermission",
            "diagnosis",
            "treatmentplan",
            "aimodel",
            "aitrainingjob",
        ):
            self.assertFalse(
                any(forbidden_model in names for names in model_names_by_app.values())
            )

        self.authenticate(self.staff)
        missing_routes = (
            "/api/predict/",
            "/api/infer/",
            "/api/train/",
            "/api/run-ai/",
            "/api/analyze-xray/",
            "/api/services/",
            "/api/service-catalog/",
            "/api/invoice-items/",
            "/api/role-permissions/",
        )
        for route in missing_routes:
            response = self.client.post(route, {}, format="json")
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, route)

    def test_environment_media_and_dependency_contracts_are_phase_15_clean(self):
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(str(settings.DATABASES["default"]["PORT"]), "5433")
        self.assertTrue(str(settings.MEDIA_ROOT).endswith("media"))
        self.assertTrue(apps.is_installed("attachments"))
        self.assertTrue(apps.is_installed("ai_results"))
        self.assertEqual(Invoice.Status.PENDING, "Pending")
        self.assertEqual(Payment.Method.CASH, "Cash")

        with open(settings.BASE_DIR / "requirements.txt", encoding="utf-8") as requirements:
            requirement_text = requirements.read().lower()

        for forbidden_dependency in (
            "torch",
            "tensorflow",
            "ultralytics",
            "opencv",
            "scikit-learn",
        ):
            self.assertNotIn(forbidden_dependency, requirement_text)
