from datetime import datetime, timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from employees.models import EmployeeProfile

from .models import AvailabilityException, WorkingShift


BASE_AT = datetime(2026, 7, 10, 9, 0, tzinfo=datetime_timezone.utc)


class AvailabilityExceptionModelTests(APITestCase):
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
            phone="+1-555-2000",
        )

    def make_exception(self, profile, start_at=None, end_at=None, **overrides):
        values = {
            "employee_profile": profile,
            "start_at": start_at or BASE_AT,
            "end_at": end_at or BASE_AT + timedelta(hours=3),
            "reason": AvailabilityException.Reason.LEAVE,
        }
        values.update(overrides)
        return AvailabilityException.objects.create(**values)

    def test_exception_can_be_created_for_doctor_employee_profile(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "doctor-leave@example.com")

        exception = self.make_exception(profile)

        self.assertEqual(exception.employee_profile, profile)
        self.assertEqual(exception.status, AvailabilityException.Status.ACTIVE)

    def test_exception_can_be_created_for_staff_employee_profile(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.STAFF, "staff-leave@example.com")

        exception = self.make_exception(profile)

        self.assertEqual(exception.employee_profile, profile)

    def test_start_at_must_be_before_end_at(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "bad-leave-time@example.com")

        with self.assertRaises(ValidationError):
            self.make_exception(
                profile,
                start_at=BASE_AT + timedelta(hours=3),
                end_at=BASE_AT + timedelta(hours=3),
            )

    def test_status_defaults_to_active(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "default-leave-status@example.com")

        exception = self.make_exception(profile)

        self.assertEqual(exception.status, AvailabilityException.Status.ACTIVE)

    def test_invalid_status_is_rejected(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "bad-leave-status@example.com")

        with self.assertRaises(ValidationError):
            self.make_exception(profile, status="Paused")

    def test_version_defaults_to_one(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "leave-version@example.com")

        exception = self.make_exception(profile)

        self.assertEqual(exception.version, 1)

    def test_active_overlapping_exception_for_same_employee_is_rejected(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "overlap-leave@example.com")
        self.make_exception(profile)

        with self.assertRaises(ValidationError):
            self.make_exception(
                profile,
                start_at=BASE_AT + timedelta(hours=2),
                end_at=BASE_AT + timedelta(hours=5),
            )

    def test_non_overlapping_same_employee_exceptions_are_allowed(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "non-overlap-leave@example.com")
        self.make_exception(profile)

        exception = self.make_exception(
            profile,
            start_at=BASE_AT + timedelta(hours=4),
            end_at=BASE_AT + timedelta(hours=6),
        )

        self.assertEqual(exception.start_at, BASE_AT + timedelta(hours=4))

    def test_boundary_touching_exceptions_are_allowed(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "boundary-leave@example.com")
        self.make_exception(profile)

        exception = self.make_exception(
            profile,
            start_at=BASE_AT + timedelta(hours=3),
            end_at=BASE_AT + timedelta(hours=6),
        )

        self.assertEqual(exception.start_at, BASE_AT + timedelta(hours=3))

    def test_overlapping_exception_on_different_employee_is_allowed(self):
        User = get_user_model()
        first = self.make_profile(User.Role.DOCTOR, "first-leave@example.com")
        second = self.make_profile(User.Role.DOCTOR, "second-leave@example.com")
        self.make_exception(first)

        exception = self.make_exception(
            second,
            start_at=BASE_AT + timedelta(hours=2),
            end_at=BASE_AT + timedelta(hours=5),
        )

        self.assertEqual(exception.employee_profile, second)

    def test_cancelled_exception_does_not_block_new_active_exception(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "cancelled-leave@example.com")
        self.make_exception(profile, status=AvailabilityException.Status.CANCELLED)

        exception = self.make_exception(
            profile,
            start_at=BASE_AT + timedelta(hours=1),
            end_at=BASE_AT + timedelta(hours=2),
        )

        self.assertEqual(exception.status, AvailabilityException.Status.ACTIVE)

    def test_setting_cancelled_back_to_active_revalidates_overlap(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "reactivate-leave@example.com")
        self.make_exception(profile)
        cancelled = self.make_exception(
            profile,
            start_at=BASE_AT + timedelta(hours=1),
            end_at=BASE_AT + timedelta(hours=2),
            status=AvailabilityException.Status.CANCELLED,
        )

        cancelled.status = AvailabilityException.Status.ACTIVE

        with self.assertRaises(ValidationError):
            cancelled.save()

    def test_working_shift_is_not_modified_by_exception_model_operations(self):
        User = get_user_model()
        profile = self.make_profile(User.Role.DOCTOR, "shift-untouched@example.com")
        shift = WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=datetime(2026, 1, 1, 9, 0).time(),
            end_time=datetime(2026, 1, 1, 12, 0).time(),
        )

        exception = self.make_exception(profile)
        exception.status = AvailabilityException.Status.CANCELLED
        exception.save()

        shift.refresh_from_db()
        self.assertTrue(shift.is_active)
        self.assertEqual(shift.version, 1)
        self.assertEqual(WorkingShift.objects.count(), 1)


class AvailabilityExceptionAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-leave@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-leave-api@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-leave-api@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-leave-api@example.com",
        )
        self.inactive = self.make_user(
            User.Role.STAFF,
            "inactive-leave-api@example.com",
            user_status=User.Status.INACTIVE,
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-2100",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-2101",
        )
        self.staff_profile = EmployeeProfile.objects.create(
            user=self.staff,
            specialty="",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-2102",
        )
        self.doctor_shift = WorkingShift.objects.create(
            employee_profile=self.doctor_profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=datetime(2026, 1, 1, 9, 0).time(),
            end_time=datetime(2026, 1, 1, 12, 0).time(),
        )
        self.doctor_exception = AvailabilityException.objects.create(
            employee_profile=self.doctor_profile,
            start_at=BASE_AT,
            end_at=BASE_AT + timedelta(hours=3),
            reason=AvailabilityException.Reason.LEAVE,
        )
        self.staff_exception = AvailabilityException.objects.create(
            employee_profile=self.staff_profile,
            start_at=BASE_AT + timedelta(days=1),
            end_at=BASE_AT + timedelta(days=1, hours=3),
            reason=AvailabilityException.Reason.TRAINING,
        )
        self.other_doctor_exception = AvailabilityException.objects.create(
            employee_profile=self.other_doctor_profile,
            start_at=BASE_AT + timedelta(days=2),
            end_at=BASE_AT + timedelta(days=2, hours=3),
            reason=AvailabilityException.Reason.PERSONAL,
        )

    def make_user(
        self,
        role,
        email,
        *,
        user_status=None,
        is_staff=False,
        is_superuser=False,
    ):
        return self.User.objects.create_user(
            username=email,
            email=email,
            password="test-pass-123",
            full_name=email.split("@")[0].replace("-", " ").title(),
            role=role,
            status=user_status or self.User.Status.ACTIVE,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def iso(self, value):
        return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")

    def payload(self, profile=None, start_at=None, end_at=None, **overrides):
        payload = {
            "employeeProfileId": (profile or self.doctor_profile).id,
            "startAt": self.iso(start_at or BASE_AT + timedelta(days=3)),
            "endAt": self.iso(end_at or BASE_AT + timedelta(days=3, hours=3)),
            "reason": "Leave",
        }
        payload.update(overrides)
        return payload

    def test_anonymous_list_is_rejected(self):
        response = self.client.get("/api/availability-exceptions/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_is_rejected(self):
        self.authenticate(self.inactive)

        response = self.client.get("/api/availability-exceptions/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_admin_can_list_retrieve_create_update_and_cancel(self):
        self.authenticate(self.admin)

        list_response = self.client.get("/api/availability-exceptions/")
        retrieve_response = self.client.get(
            f"/api/availability-exceptions/{self.doctor_exception.id}/"
        )
        create_response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(reason="Emergency"),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {
                "note": "Updated by admin",
                "version": self.doctor_exception.version,
            },
            format="json",
        )
        cancel_response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {
                "status": "Cancelled",
                "version": update_response.data["version"],
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data["results"]), 3)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["version"], 2)
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data["status"], "Cancelled")
        self.assertIsNotNone(cancel_response.data["cancelledAt"])

    def test_staff_can_list_and_retrieve(self):
        self.authenticate(self.staff)

        list_response = self.client.get("/api/availability-exceptions/")
        retrieve_response = self.client.get(
            f"/api/availability-exceptions/{self.doctor_exception.id}/"
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_create_update_or_cancel(self):
        self.authenticate(self.staff)

        create_response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/availability-exceptions/{self.staff_exception.id}/",
            {"note": "Not allowed", "version": self.staff_exception.version},
            format="json",
        )
        cancel_response = self.client.patch(
            f"/api/availability-exceptions/{self.staff_exception.id}/",
            {"status": "Cancelled", "version": self.staff_exception.version},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(cancel_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_list_and_retrieve_own_exceptions(self):
        self.authenticate(self.doctor)

        list_response = self.client.get("/api/availability-exceptions/")
        retrieve_response = self.client.get(
            f"/api/availability-exceptions/{self.doctor_exception.id}/"
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in list_response.data["results"]],
            [self.doctor_exception.id],
        )

    def test_doctor_cannot_list_or_retrieve_other_employee_exceptions(self):
        self.authenticate(self.doctor)

        list_response = self.client.get(
            "/api/availability-exceptions/",
            {"employeeProfileId": self.other_doctor_profile.id},
        )
        retrieve_response = self.client.get(
            f"/api/availability-exceptions/{self.other_doctor_exception.id}/"
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["results"], [])
        self.assertEqual(retrieve_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_create_update_or_cancel(self):
        self.authenticate(self.doctor)

        create_response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {"note": "Not allowed", "version": self.doctor_exception.version},
            format="json",
        )
        cancel_response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {"status": "Cancelled", "version": self.doctor_exception.version},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(cancel_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_exception_returns_camel_case_fields(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(reason="Sick Leave", note="Flu"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("employeeProfileId", response.data)
        self.assertIn("startAt", response.data)
        self.assertIn("endAt", response.data)
        self.assertIn("createdAt", response.data)
        self.assertIn("updatedAt", response.data)
        self.assertNotIn("employee_profile", response.data)
        self.assertNotIn("start_at", response.data)
        self.assertNotIn("isOnLeave", response.data)
        self.assertEqual(response.data["userId"], self.doctor.id)
        self.assertEqual(response.data["fullName"], self.doctor.full_name)
        self.assertEqual(response.data["role"], "Doctor")
        self.assertEqual(response.data["specialty"], "Endodontics")
        self.assertEqual(response.data["reason"], "Sick Leave")
        self.assertEqual(response.data["note"], "Flu")
        self.assertEqual(response.data["createdBy"], self.admin.id)

    def test_list_supports_employee_profile_filter(self):
        self.authenticate(self.admin)

        response = self.client.get(
            "/api/availability-exceptions/",
            {"employeeProfileId": self.staff_profile.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.staff_exception.id],
        )

    def test_list_supports_role_filter(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/availability-exceptions/", {"role": "Staff"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertEqual({item["role"] for item in response.data["results"]}, {"Staff"})

    def test_list_supports_status_filter(self):
        self.authenticate(self.admin)
        cancelled = AvailabilityException.objects.create(
            employee_profile=self.staff_profile,
            start_at=BASE_AT + timedelta(days=4),
            end_at=BASE_AT + timedelta(days=4, hours=3),
            reason=AvailabilityException.Reason.OTHER,
            status=AvailabilityException.Status.CANCELLED,
        )

        response = self.client.get(
            "/api/availability-exceptions/",
            {"status": "Cancelled"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["results"]], [cancelled.id])

    def test_list_supports_from_to_overlap_window_filter(self):
        self.authenticate(self.admin)

        response = self.client.get(
            "/api/availability-exceptions/",
            {
                "from": self.iso(BASE_AT + timedelta(hours=1)),
                "to": self.iso(BASE_AT + timedelta(hours=2)),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.doctor_exception.id],
        )

    def test_patch_with_correct_version_succeeds_and_increments_version(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {
                "reason": "Training",
                "version": self.doctor_exception.version,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], 2)
        self.doctor_exception.refresh_from_db()
        self.assertEqual(self.doctor_exception.reason, "Training")
        self.assertEqual(self.doctor_exception.version, 2)

    def test_patch_with_stale_version_returns_409(self):
        self.authenticate(self.admin)
        self.doctor_exception.version = 3
        self.doctor_exception.save()

        response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {"reason": "Training", "version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Version conflict")
        self.assertEqual(response.data["currentVersion"], 3)

    def test_patch_without_version_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {"reason": "Training"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", response.data)

    def test_invalid_datetime_interval_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(
                start_at=BASE_AT + timedelta(days=5, hours=3),
                end_at=BASE_AT + timedelta(days=5),
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_at", response.data)

    def test_overlap_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(
                start_at=BASE_AT + timedelta(hours=1),
                end_at=BASE_AT + timedelta(hours=4),
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_cancelling_via_patch_status_cancelled_works(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/availability-exceptions/{self.doctor_exception.id}/",
            {
                "status": "Cancelled",
                "version": self.doctor_exception.version,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "Cancelled")
        self.assertIsNotNone(response.data["cancelledAt"])
        self.assertEqual(response.data["cancelledBy"], self.admin.id)

    def test_cancelled_exception_no_longer_blocks_new_active_exception(self):
        self.authenticate(self.admin)
        self.doctor_exception.status = AvailabilityException.Status.CANCELLED
        self.doctor_exception.save()

        response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(
                start_at=BASE_AT + timedelta(hours=1),
                end_at=BASE_AT + timedelta(hours=2),
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_reactivating_cancelled_exception_revalidates_overlap(self):
        self.authenticate(self.admin)
        cancelled = AvailabilityException.objects.create(
            employee_profile=self.doctor_profile,
            start_at=BASE_AT + timedelta(hours=1),
            end_at=BASE_AT + timedelta(hours=2),
            reason=AvailabilityException.Reason.OTHER,
            status=AvailabilityException.Status.CANCELLED,
        )

        response = self.client.patch(
            f"/api/availability-exceptions/{cancelled.id}/",
            {
                "status": "Active",
                "version": cancelled.version,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_working_shift_is_not_modified_by_exception_api_operations(self):
        self.authenticate(self.admin)
        original_shift_values = (
            self.doctor_shift.is_active,
            self.doctor_shift.start_time,
            self.doctor_shift.end_time,
            self.doctor_shift.version,
        )

        create_response = self.client.post(
            "/api/availability-exceptions/",
            self.payload(start_at=BASE_AT + timedelta(days=5), end_at=BASE_AT + timedelta(days=5, hours=3)),
            format="json",
        )
        patch_response = self.client.patch(
            f"/api/availability-exceptions/{create_response.data['id']}/",
            {
                "status": "Cancelled",
                "version": create_response.data["version"],
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.doctor_shift.refresh_from_db()
        self.assertEqual(
            (
                self.doctor_shift.is_active,
                self.doctor_shift.start_time,
                self.doctor_shift.end_time,
                self.doctor_shift.version,
            ),
            original_shift_values,
        )
        self.assertEqual(WorkingShift.objects.count(), 1)

    def test_working_shifts_endpoint_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/working-shifts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_source_leave_exceptions_alias_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/leave-exceptions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
