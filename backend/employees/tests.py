from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer


class EmployeeProfileModelSerializerTests(APITestCase):
    def make_user(self, role, email):
        User = get_user_model()
        return User.objects.create_user(
            username=email,
            email=email,
            password="test-pass-123",
            full_name=email.split("@")[0].replace("-", " ").replace(".", " ").title(),
            role=role,
            status=User.Status.ACTIVE,
            is_staff=role == User.Role.ADMIN,
            is_superuser=role == User.Role.ADMIN,
        )

    def test_doctor_profile_can_be_created_for_doctor_user(self):
        User = get_user_model()
        doctor = self.make_user(User.Role.DOCTOR, "doctor-profile@example.com")

        profile = EmployeeProfile.objects.create(
            user=doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-1000",
            avatar_url="https://example.com/avatar.png",
        )

        self.assertEqual(profile.user, doctor)
        self.assertEqual(profile.specialty, "Endodontics")
        self.assertEqual(profile.version, 1)

    def test_staff_profile_can_be_created_for_staff_user(self):
        User = get_user_model()
        staff = self.make_user(User.Role.STAFF, "staff-profile@example.com")

        profile = EmployeeProfile.objects.create(
            user=staff,
            specialty="",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-1001",
        )

        self.assertEqual(profile.user, staff)
        self.assertEqual(profile.specialty, "")

    def test_admin_user_cannot_have_employee_profile(self):
        User = get_user_model()
        admin = self.make_user(User.Role.ADMIN, "admin-profile@example.com")

        with self.assertRaises(ValidationError):
            EmployeeProfile(
                user=admin,
                gender=EmployeeProfile.Gender.FEMALE,
            ).full_clean()

    def test_duplicate_profile_for_same_user_is_rejected(self):
        User = get_user_model()
        doctor = self.make_user(User.Role.DOCTOR, "duplicate-profile@example.com")
        EmployeeProfile.objects.create(
            user=doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
        )

        with self.assertRaises(ValidationError):
            EmployeeProfile.objects.create(
                user=doctor,
                specialty="Orthodontics",
                gender=EmployeeProfile.Gender.MALE,
            )

    def test_doctor_specialty_is_required(self):
        User = get_user_model()
        doctor = self.make_user(User.Role.DOCTOR, "no-specialty@example.com")

        with self.assertRaises(ValidationError):
            EmployeeProfile(
                user=doctor,
                specialty="",
                gender=EmployeeProfile.Gender.FEMALE,
            ).full_clean()

    def test_staff_specialty_is_rejected(self):
        User = get_user_model()
        staff = self.make_user(User.Role.STAFF, "staff-specialty@example.com")

        with self.assertRaises(ValidationError):
            EmployeeProfile(
                user=staff,
                specialty="Reception",
                gender=EmployeeProfile.Gender.FEMALE,
            ).full_clean()

    def test_serializer_uses_camel_case_and_user_fields(self):
        User = get_user_model()
        doctor = self.make_user(User.Role.DOCTOR, "camel-profile@example.com")
        profile = EmployeeProfile.objects.create(
            user=doctor,
            specialty="Pediatric Dentistry",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-1002",
            avatar_url="https://example.com/camel.png",
        )

        data = EmployeeProfileSerializer(profile).data

        self.assertEqual(data["userId"], doctor.id)
        self.assertEqual(data["username"], "camel-profile@example.com")
        self.assertEqual(data["fullName"], "Camel Profile")
        self.assertEqual(data["email"], "camel-profile@example.com")
        self.assertEqual(data["role"], "Doctor")
        self.assertEqual(data["status"], "Active")
        self.assertEqual(data["avatarUrl"], "https://example.com/camel.png")
        self.assertIn("createdAt", data)
        self.assertIn("updatedAt", data)
        self.assertNotIn("avatar_url", data)

    def test_version_defaults_to_one(self):
        User = get_user_model()
        doctor = self.make_user(User.Role.DOCTOR, "version-profile@example.com")

        profile = EmployeeProfile.objects.create(
            user=doctor,
            specialty="Periodontics",
            gender=EmployeeProfile.Gender.MALE,
        )

        self.assertEqual(profile.version, 1)


class EmployeeProfileAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-employee@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-employee@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-employee@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-employee@example.com",
        )
        self.inactive = self.make_user(
            User.Role.STAFF,
            "inactive-employee@example.com",
            status=User.Status.INACTIVE,
            is_active=False,
        )
        self.doctor_without_profile = self.make_user(
            User.Role.DOCTOR,
            "new-doctor-employee@example.com",
        )
        self.staff_without_profile = self.make_user(
            User.Role.STAFF,
            "new-staff-employee@example.com",
        )
        self.admin_target = self.make_user(
            User.Role.ADMIN,
            "target-admin-employee@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff_profile = EmployeeProfile.objects.create(
            user=self.staff,
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-2001",
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-2002",
            avatar_url="https://example.com/doctor.png",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-2003",
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
            full_name=email.split("@")[0].replace("-", " ").replace(".", " ").title(),
            role=role,
            status=status or User.Status.ACTIVE,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def doctor_payload(self, user=None, **overrides):
        payload = {
            "userId": (user or self.doctor_without_profile).id,
            "specialty": "Prosthodontics",
            "gender": "Female",
            "phone": "+1-555-3000",
            "avatarUrl": "https://example.com/new-doctor.png",
        }
        payload.update(overrides)
        return payload

    def staff_payload(self, user=None, **overrides):
        payload = {
            "userId": (user or self.staff_without_profile).id,
            "gender": "Male",
            "phone": "+1-555-3001",
            "avatarUrl": "",
        }
        payload.update(overrides)
        return payload

    def test_anonymous_list_is_rejected(self):
        response = self.client.get("/api/employee-profiles/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_is_rejected(self):
        self.authenticate(self.inactive)

        response = self.client.get("/api/employee-profiles/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_admin_can_list_retrieve_create_and_update_profiles(self):
        self.authenticate(self.admin)

        list_response = self.client.get("/api/employee-profiles/")
        retrieve_response = self.client.get(
            f"/api/employee-profiles/{self.doctor_profile.id}/"
        )
        create_response = self.client.post(
            "/api/employee-profiles/",
            self.doctor_payload(),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/employee-profiles/{self.staff_profile.id}/",
            {"phone": "+1-555-9999", "version": self.staff_profile.version},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["phone"], "+1-555-9999")

    def test_staff_can_list_and_retrieve_profiles(self):
        self.authenticate(self.staff)

        list_response = self.client.get("/api/employee-profiles/")
        retrieve_response = self.client.get(
            f"/api/employee-profiles/{self.doctor_profile.id}/"
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_create_or_update_profiles(self):
        self.authenticate(self.staff)

        create_response = self.client.post(
            "/api/employee-profiles/",
            self.doctor_payload(),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/employee-profiles/{self.doctor_profile.id}/",
            {"phone": "+1-555-9999", "version": self.doctor_profile.version},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_get_own_profile_through_me(self):
        self.authenticate(self.doctor)

        response = self.client.get("/api/employee-profiles/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.doctor_profile.id)

    def test_doctor_can_retrieve_own_profile_by_id(self):
        self.authenticate(self.doctor)

        response = self.client.get(f"/api/employee-profiles/{self.doctor_profile.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["userId"], self.doctor.id)

    def test_doctor_cannot_list_all_profiles(self):
        self.authenticate(self.doctor)

        response = self.client.get("/api/employee-profiles/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_retrieve_another_profile(self):
        self.authenticate(self.doctor)

        response = self.client.get(
            f"/api/employee-profiles/{self.other_doctor_profile.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_create_or_update_profiles(self):
        self.authenticate(self.doctor)

        create_response = self.client.post(
            "/api/employee-profiles/",
            self.staff_payload(),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/employee-profiles/{self.doctor_profile.id}/",
            {"phone": "+1-555-9999", "version": self.doctor_profile.version},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_profile_for_existing_doctor_user_returns_profile_data(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/employee-profiles/",
            self.doctor_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["userId"], self.doctor_without_profile.id)
        self.assertEqual(response.data["role"], "Doctor")
        self.assertEqual(response.data["specialty"], "Prosthodontics")
        self.assertEqual(response.data["version"], 1)

    def test_create_profile_for_existing_staff_user_returns_profile_data(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/employee-profiles/",
            self.staff_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["userId"], self.staff_without_profile.id)
        self.assertEqual(response.data["role"], "Staff")
        self.assertEqual(response.data["specialty"], "")

    def test_create_profile_for_admin_user_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/employee-profiles/",
            self.staff_payload(user=self.admin_target),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("userId", response.data)

    def test_create_profile_for_nonexistent_user_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/employee-profiles/",
            self.doctor_payload(user=self.doctor_without_profile, userId=999999),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("userId", response.data)

    def test_duplicate_profile_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/employee-profiles/",
            self.doctor_payload(user=self.doctor),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("userId", response.data)

    def assert_search_finds_profile(self, search, profile):
        response = self.client.get("/api/employee-profiles/", {"search": search})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertIn(profile.id, ids)

    def test_search_by_username_works(self):
        self.authenticate(self.admin)

        self.assert_search_finds_profile("doctor-employee", self.doctor_profile)

    def test_search_by_full_name_works(self):
        self.authenticate(self.admin)

        self.assert_search_finds_profile("Doctor Employee", self.doctor_profile)

    def test_search_by_email_works(self):
        self.authenticate(self.admin)

        self.assert_search_finds_profile("doctor-employee@example.com", self.doctor_profile)

    def test_search_by_specialty_works(self):
        self.authenticate(self.admin)

        self.assert_search_finds_profile("Endodontics", self.doctor_profile)

    def test_role_filter_for_doctor_works(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/employee-profiles/", {"role": "Doctor"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertEqual({item["role"] for item in response.data["results"]}, {"Doctor"})

    def test_role_filter_for_staff_works(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/employee-profiles/", {"role": "Staff"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertEqual({item["role"] for item in response.data["results"]}, {"Staff"})

    def test_patch_with_correct_version_succeeds_and_increments_version(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/employee-profiles/{self.doctor_profile.id}/",
            {"phone": "+1-555-8888", "version": self.doctor_profile.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], 2)
        self.doctor_profile.refresh_from_db()
        self.assertEqual(self.doctor_profile.phone, "+1-555-8888")
        self.assertEqual(self.doctor_profile.version, 2)

    def test_patch_with_stale_version_returns_409(self):
        self.authenticate(self.admin)
        self.doctor_profile.version = 3
        self.doctor_profile.save()

        response = self.client.patch(
            f"/api/employee-profiles/{self.doctor_profile.id}/",
            {"phone": "+1-555-8888", "version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Version conflict")
        self.assertEqual(response.data["currentVersion"], 3)

    def test_patch_without_version_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/employee-profiles/{self.doctor_profile.id}/",
            {"phone": "+1-555-8888"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", response.data)

    def test_invalid_profile_role_is_rejected(self):
        self.authenticate(self.admin)

        response = self.client.get("/api/employee-profiles/", {"role": "Admin"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_health_endpoint_remains_public(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_auth_me_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "staff-employee@example.com")

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
