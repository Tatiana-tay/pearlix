from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from types import SimpleNamespace

from .permissions import (
    IsActiveUser,
    IsAdminOrStaff,
    IsAdminRole,
    IsDoctorRole,
    IsStaffOrDoctor,
    IsStaffRole,
    is_active_user,
    is_admin,
    is_doctor,
    is_staff_role,
)


class UserModelTests(TestCase):
    def test_custom_user_can_be_created_with_phase_0a_fields(self):
        User = get_user_model()

        user = User.objects.create_user(
            username="doctor.one",
            email="doctor@example.com",
            password="test-pass-123",
            full_name="Doctor One",
            role=User.Role.DOCTOR,
            status=User.Status.ACTIVE,
            must_change_password=True,
        )

        self.assertEqual(user.full_name, "Doctor One")
        self.assertEqual(user.email, "doctor@example.com")
        self.assertEqual(user.role, User.Role.DOCTOR)
        self.assertEqual(user.status, User.Status.ACTIVE)
        self.assertTrue(user.must_change_password)

    def test_email_uniqueness_is_enforced(self):
        User = get_user_model()
        User.objects.create_user(
            username="staff.one",
            email="shared@example.com",
            password="test-pass-123",
            full_name="Staff One",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="staff.two",
                    email="shared@example.com",
                    password="test-pass-123",
                    full_name="Staff Two",
                )


class SeedDevUsersTests(TestCase):
    def test_seed_dev_users_creates_expected_users_without_duplicates(self):
        User = get_user_model()
        emails = [
            "admin@example.com",
            "staff@example.com",
            "doctor@example.com",
            "inactive@example.com",
        ]

        call_command("seed_dev_users", verbosity=0)
        call_command("seed_dev_users", verbosity=0)

        self.assertEqual(User.objects.filter(email__in=emails).count(), 4)

        admin = User.objects.get(email="admin@example.com")
        self.assertEqual(admin.username, "admin@example.com")
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertEqual(admin.status, User.Status.ACTIVE)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertFalse(admin.must_change_password)

        staff = User.objects.get(email="staff@example.com")
        self.assertEqual(staff.role, User.Role.STAFF)
        self.assertEqual(staff.status, User.Status.ACTIVE)
        self.assertFalse(staff.is_staff)

        doctor = User.objects.get(email="doctor@example.com")
        self.assertEqual(doctor.role, User.Role.DOCTOR)
        self.assertEqual(doctor.status, User.Status.ACTIVE)
        self.assertFalse(doctor.is_staff)

        inactive = User.objects.get(email="inactive@example.com")
        self.assertEqual(inactive.role, User.Role.STAFF)
        self.assertEqual(inactive.status, User.Status.INACTIVE)
        self.assertFalse(inactive.is_active)


class AuthEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_dev_users", verbosity=0)

    def setUp(self):
        self.client.defaults["HTTP_HOST"] = "localhost"

    def login(self, username, password):
        return self.client.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
        )

    def auth_headers_for(self, username, password):
        response = self.login(username, password)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}

    def test_login_succeeds_for_active_admin(self):
        response = self.login("admin@example.com", "Admin123!")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], "Admin")
        self.assertFalse(response.data["user"]["mustChangePassword"])

    def test_login_succeeds_for_active_staff(self):
        response = self.login("staff@example.com", "Staff123!")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"], "Staff")

    def test_login_succeeds_for_active_doctor(self):
        response = self.login("doctor@example.com", "Doctor123!")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"], "Doctor")

    def test_login_fails_for_inactive_user(self):
        response = self.login("inactive@example.com", "Inactive123!")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_returns_authenticated_user(self):
        headers = self.auth_headers_for("admin@example.com", "Admin123!")

        response = self.client.get("/api/auth/me/", **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "admin@example.com")
        self.assertEqual(response.data["fullName"], "Admin User")
        self.assertEqual(response.data["role"], "Admin")
        self.assertEqual(response.data["status"], "Active")
        self.assertFalse(response.data["mustChangePassword"])

    def test_me_rejects_unauthenticated_request(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_roles_returns_fixed_roles(self):
        headers = self.auth_headers_for("staff@example.com", "Staff123!")

        response = self.client.get("/api/auth/roles/", **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"roles": ["Admin", "Staff", "Doctor"]})

    def test_refresh_endpoint_works(self):
        login_response = self.login("doctor@example.com", "Doctor123!")

        response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_logout_endpoint_returns_success(self):
        headers = self.auth_headers_for("admin@example.com", "Admin123!")

        response = self.client.post("/api/auth/logout/", {}, format="json", **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])


class RolePermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin-role@example.com",
            email="admin-role@example.com",
            password="test-pass-123",
            full_name="Admin Role",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        self.staff = User.objects.create_user(
            username="staff-role@example.com",
            email="staff-role@example.com",
            password="test-pass-123",
            full_name="Staff Role",
            role=User.Role.STAFF,
            status=User.Status.ACTIVE,
        )
        self.doctor = User.objects.create_user(
            username="doctor-role@example.com",
            email="doctor-role@example.com",
            password="test-pass-123",
            full_name="Doctor Role",
            role=User.Role.DOCTOR,
            status=User.Status.ACTIVE,
        )
        self.inactive = User.objects.create_user(
            username="inactive-role@example.com",
            email="inactive-role@example.com",
            password="test-pass-123",
            full_name="Inactive Role",
            role=User.Role.STAFF,
            status=User.Status.INACTIVE,
            is_active=False,
        )
        self.django_staff_doctor = User.objects.create_user(
            username="django-staff-doctor@example.com",
            email="django-staff-doctor@example.com",
            password="test-pass-123",
            full_name="Django Staff Doctor",
            role=User.Role.DOCTOR,
            status=User.Status.ACTIVE,
            is_staff=True,
        )

    def allows(self, permission_class, user):
        request = SimpleNamespace(user=user)
        return permission_class().has_permission(request, view=None)

    def test_anonymous_user_fails_role_permission_checks(self):
        anonymous = AnonymousUser()

        self.assertFalse(self.allows(IsAdminRole, anonymous))
        self.assertFalse(self.allows(IsStaffRole, anonymous))
        self.assertFalse(self.allows(IsDoctorRole, anonymous))
        self.assertFalse(self.allows(IsAdminOrStaff, anonymous))
        self.assertFalse(self.allows(IsStaffOrDoctor, anonymous))

    def test_inactive_user_fails_active_user_permission_checks(self):
        self.assertFalse(is_active_user(self.inactive))
        self.assertFalse(self.allows(IsActiveUser, self.inactive))
        self.assertFalse(self.allows(IsStaffRole, self.inactive))

    def test_admin_passes_admin_permission(self):
        self.assertTrue(is_admin(self.admin))
        self.assertTrue(self.allows(IsAdminRole, self.admin))

    def test_staff_role_passes_staff_permission(self):
        self.assertTrue(is_staff_role(self.staff))
        self.assertTrue(self.allows(IsStaffRole, self.staff))

    def test_doctor_role_passes_doctor_permission(self):
        self.assertTrue(is_doctor(self.doctor))
        self.assertTrue(self.allows(IsDoctorRole, self.doctor))

    def test_staff_does_not_pass_admin_permission(self):
        self.assertFalse(self.allows(IsAdminRole, self.staff))

    def test_doctor_does_not_pass_staff_permission(self):
        self.assertFalse(self.allows(IsStaffRole, self.doctor))

    def test_admin_or_staff_allows_admin_and_staff(self):
        self.assertTrue(self.allows(IsAdminOrStaff, self.admin))
        self.assertTrue(self.allows(IsAdminOrStaff, self.staff))

    def test_admin_or_staff_rejects_doctor(self):
        self.assertFalse(self.allows(IsAdminOrStaff, self.doctor))

    def test_staff_or_doctor_allows_staff_and_doctor(self):
        self.assertTrue(self.allows(IsStaffOrDoctor, self.staff))
        self.assertTrue(self.allows(IsStaffOrDoctor, self.doctor))

    def test_staff_or_doctor_rejects_admin(self):
        self.assertFalse(self.allows(IsStaffOrDoctor, self.admin))

    def test_django_is_staff_is_not_clinic_staff_role(self):
        self.assertTrue(self.django_staff_doctor.is_staff)
        self.assertEqual(self.django_staff_doctor.role, "Doctor")
        self.assertFalse(is_staff_role(self.django_staff_doctor))
        self.assertFalse(self.allows(IsStaffRole, self.django_staff_doctor))
        self.assertTrue(self.allows(IsDoctorRole, self.django_staff_doctor))
