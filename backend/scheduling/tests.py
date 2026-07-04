from datetime import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from employees.models import EmployeeProfile

from .models import WorkingShift


class WorkingShiftModelTests(APITestCase):
    def make_user(self, role, email):
        User = get_user_model()
        return User.objects.create_user(
            username=email,
            email=email,
            password="test-pass-123",
            full_name=email.split("@")[0].replace("-", " ").title(),
            role=role,
            status=User.Status.ACTIVE,
            is_staff=role == User.Role.ADMIN,
            is_superuser=role == User.Role.ADMIN,
        )

    def make_profile(self, role, email, specialty="Endodontics"):
        User = get_user_model()
        user = self.make_user(role, email)
        return EmployeeProfile.objects.create(
            user=user,
            specialty=specialty if role == User.Role.DOCTOR else "",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-1000",
        )

    def test_shift_can_be_created_for_doctor_employee_profile(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "doctor-shift@example.com")

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        self.assertEqual(shift.employee_profile, profile)
        self.assertTrue(shift.is_active)

    def test_shift_can_be_created_for_staff_employee_profile(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.STAFF, "staff-shift@example.com")

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.TUESDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        self.assertEqual(shift.employee_profile, profile)

    def test_start_time_must_be_before_end_time(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "bad-time-shift@example.com")

        with self.assertRaises(ValidationError):
            WorkingShift.objects.create(
                employee_profile=profile,
                day_of_week=WorkingShift.DayOfWeek.MONDAY,
                start_time=time(12, 0),
                end_time=time(12, 0),
            )

    def test_invalid_day_of_week_is_rejected(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "bad-day-shift@example.com")

        with self.assertRaises(ValidationError):
            WorkingShift.objects.create(
                employee_profile=profile,
                day_of_week="Funday",
                start_time=time(9, 0),
                end_time=time(12, 0),
            )

    def test_is_active_defaults_true(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "active-default@example.com")

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        self.assertTrue(shift.is_active)

    def test_version_defaults_to_one(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "version-shift@example.com")

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        self.assertEqual(shift.version, 1)

    def test_active_overlapping_shift_for_same_employee_day_is_rejected(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "overlap-shift@example.com")
        WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        with self.assertRaises(ValidationError):
            WorkingShift.objects.create(
                employee_profile=profile,
                day_of_week=WorkingShift.DayOfWeek.MONDAY,
                start_time=time(11, 30),
                end_time=time(14, 0),
            )

    def test_non_overlapping_same_day_shifts_are_allowed(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "non-overlap-shift@example.com")
        WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(13, 0),
            end_time=time(15, 0),
        )

        self.assertEqual(shift.start_time, time(13, 0))

    def test_boundary_touching_shifts_are_allowed(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "boundary-shift@example.com")
        WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(12, 0),
            end_time=time(15, 0),
        )

        self.assertEqual(shift.start_time, time(12, 0))

    def test_overlapping_shift_on_different_employee_is_allowed(self):
        User = get_user_model()
        first = self.make_profile(User.Role.DOCTOR, "first-shift@example.com")
        second = self.make_profile(User.Role.DOCTOR, "second-shift@example.com")
        WorkingShift.objects.create(
            employee_profile=first,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        shift = WorkingShift.objects.create(
            employee_profile=second,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(11, 30),
            end_time=time(14, 0),
        )

        self.assertEqual(shift.employee_profile, second)

    def test_overlapping_shift_on_different_day_is_allowed(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "different-day-shift@example.com")
        WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.TUESDAY,
            start_time=time(11, 30),
            end_time=time(14, 0),
        )

        self.assertEqual(shift.day_of_week, "Tuesday")

    def test_inactive_overlapping_shift_does_not_block_active_shift(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "inactive-overlap@example.com")
        WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_active=False,
        )

        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )

        self.assertTrue(shift.is_active)


class WorkingShiftAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-schedule@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-schedule@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-schedule@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-schedule@example.com",
        )
        self.inactive = self.make_user(
            User.Role.STAFF,
            "inactive-schedule@example.com",
            status=User.Status.INACTIVE,
            is_active=False,
        )
        self.staff_profile = self.make_profile(self.staff)
        self.doctor_profile = self.make_profile(self.doctor, specialty="Endodontics")
        self.other_doctor_profile = self.make_profile(
            self.other_doctor,
            specialty="Orthodontics",
        )
        self.doctor_shift = WorkingShift.objects.create(
            employee_profile=self.doctor_profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        self.staff_shift = WorkingShift.objects.create(
            employee_profile=self.staff_profile,
            day_of_week=WorkingShift.DayOfWeek.TUESDAY,
            start_time=time(8, 0),
            end_time=time(11, 0),
        )
        self.other_doctor_shift = WorkingShift.objects.create(
            employee_profile=self.other_doctor_profile,
            day_of_week=WorkingShift.DayOfWeek.WEDNESDAY,
            start_time=time(13, 0),
            end_time=time(16, 0),
        )

    def make_user(
        self,
        role,
        email,
        *,
        status=None,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    ):
        User = get_user_model()
        return User.objects.create_user(
            username=email,
            email=email,
            password="test-pass-123",
            full_name=email.split("@")[0].replace("-", " ").title(),
            role=role,
            status=status or User.Status.ACTIVE,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )

    def make_profile(self, user, specialty=""):
        return EmployeeProfile.objects.create(
            user=user,
            specialty=specialty,
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-2000",
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def payload(self, profile=None, **overrides):
        payload = {
            "employeeProfileId": (profile or self.doctor_profile).id,
            "dayOfWeek": "Thursday",
            "startTime": "09:00",
            "endTime": "12:00",
        }
        payload.update(overrides)
        return payload

    def test_anonymous_list_is_rejected(self):
        response = self.client.get("/api/working-shifts/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_is_rejected(self):
        self.authenticate(self.inactive)

        response = self.client.get("/api/working-shifts/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_admin_can_list_retrieve_create_and_update(self):
        self.authenticate(self.admin)

        list_response = self.client.get("/api/working-shifts/")
        retrieve_response = self.client.get(f"/api/working-shifts/{self.doctor_shift.id}/")
        create_response = self.client.post(
            "/api/working-shifts/",
            self.payload(dayOfWeek="Friday"),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/working-shifts/{self.doctor_shift.id}/",
            {"endTime": "12:30", "version": self.doctor_shift.version},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["endTime"], "12:30")

    def test_staff_can_list_and_retrieve(self):
        self.authenticate(self.staff)

        list_response = self.client.get("/api/working-shifts/")
        retrieve_response = self.client.get(f"/api/working-shifts/{self.doctor_shift.id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_create_or_update(self):
        self.authenticate(self.staff)

        create_response = self.client.post(
            "/api/working-shifts/",
            self.payload(dayOfWeek="Friday"),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/working-shifts/{self.staff_shift.id}/",
            {"endTime": "11:30", "version": self.staff_shift.version},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_list_and_retrieve_own_shifts(self):
        self.authenticate(self.doctor)

        list_response = self.client.get("/api/working-shifts/")
        retrieve_response = self.client.get(f"/api/working-shifts/{self.doctor_shift.id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [self.doctor_shift.id])

    def test_doctor_cannot_list_or_retrieve_other_employee_shifts(self):
        self.authenticate(self.doctor)

        list_response = self.client.get(
            "/api/working-shifts/",
            {"employeeProfileId": self.other_doctor_profile.id},
        )
        retrieve_response = self.client.get(
            f"/api/working-shifts/{self.other_doctor_shift.id}/"
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["results"], [])
        self.assertEqual(retrieve_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_create_or_update(self):
        self.authenticate(self.doctor)

        create_response = self.client.post(
            "/api/working-shifts/",
            self.payload(dayOfWeek="Friday"),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/working-shifts/{self.doctor_shift.id}/",
            {"endTime": "12:30", "version": self.doctor_shift.version},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_shift_returns_camel_case_fields(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/working-shifts/",
            self.payload(dayOfWeek="Friday"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("employeeProfileId", response.data)
        self.assertIn("dayOfWeek", response.data)
        self.assertIn("startTime", response.data)
        self.assertIn("endTime", response.data)
        self.assertIn("isActive", response.data)
        self.assertIn("createdAt", response.data)
        self.assertIn("updatedAt", response.data)
        self.assertNotIn("employee_profile", response.data)
        self.assertNotIn("isOnLeave", response.data)
        self.assertEqual(response.data["userId"], self.doctor.id)
        self.assertEqual(response.data["fullName"], self.doctor.full_name)
        self.assertEqual(response.data["role"], "Doctor")
        self.assertEqual(response.data["specialty"], "Endodontics")

    def test_list_supports_employee_profile_filter(self):
        self.authenticate(self.admin)

        response = self.client.get(
            "/api/working-shifts/",
            {"employeeProfileId": self.staff_profile.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["results"]], [self.staff_shift.id])

    def test_list_supports_role_filter(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/working-shifts/", {"role": "Staff"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertEqual({item["role"] for item in response.data["results"]}, {"Staff"})

    def test_list_supports_day_of_week_filter(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/working-shifts/", {"dayOfWeek": "Monday"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["results"]], [self.doctor_shift.id])

    def test_list_supports_is_active_filter(self):
        self.authenticate(self.admin)
        inactive_shift = WorkingShift.objects.create(
            employee_profile=self.staff_profile,
            day_of_week=WorkingShift.DayOfWeek.FRIDAY,
            start_time=time(13, 0),
            end_time=time(16, 0),
            is_active=False,
        )

        response = self.client.get("/api/working-shifts/", {"isActive": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["results"]], [inactive_shift.id])

    def test_patch_with_correct_version_succeeds_and_increments_version(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/working-shifts/{self.doctor_shift.id}/",
            {"endTime": "12:30", "version": self.doctor_shift.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], 2)
        self.doctor_shift.refresh_from_db()
        self.assertEqual(self.doctor_shift.end_time, time(12, 30))
        self.assertEqual(self.doctor_shift.version, 2)

    def test_patch_with_stale_version_returns_409(self):
        self.authenticate(self.admin)
        self.doctor_shift.version = 3
        self.doctor_shift.save()

        response = self.client.patch(
            f"/api/working-shifts/{self.doctor_shift.id}/",
            {"endTime": "12:30", "version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Version conflict")
        self.assertEqual(response.data["currentVersion"], 3)

    def test_patch_without_version_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/working-shifts/{self.doctor_shift.id}/",
            {"endTime": "12:30"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", response.data)

    def test_invalid_time_interval_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/working-shifts/",
            self.payload(startTime="12:00", endTime="09:00"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_time", response.data)

    def test_overlap_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/working-shifts/",
            self.payload(
                dayOfWeek="Monday",
                startTime="11:30",
                endTime="14:00",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_time", response.data)

    def test_deactivating_shift_via_patch_is_active_false_works(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/working-shifts/{self.doctor_shift.id}/",
            {"isActive": False, "version": self.doctor_shift.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["isActive"])

    def test_health_endpoint_remains_public(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_auth_me_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "staff-schedule@example.com")

    def test_auth_roles_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/auth/roles/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"roles": ["Admin", "Staff", "Doctor"]})

    def test_clinic_settings_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/clinic/settings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("clinicTimezone", response.data)

    def test_patients_endpoint_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/patients/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_employee_profiles_endpoint_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/employee-profiles/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
