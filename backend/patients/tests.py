from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Patient
from .serializers import PatientSerializer


class PatientModelSerializerTests(APITestCase):
    def test_patient_can_be_created_with_source_aligned_fields(self):
        patient = Patient.objects.create(
            first_name="Maya",
            last_name="Haddad",
            gender=Patient.Gender.FEMALE,
            date_of_birth=date(1991, 5, 20),
            phone_number="+1-555-0100",
            email="maya@example.com",
            national_id_or_passport="P-100",
            medical_conditions_history="None",
            blood_group=Patient.BloodGroup.O_POSITIVE,
            insurance_info="Plan A",
            emergency_contact="+1-555-0109",
            address="10 Main Street",
        )

        self.assertEqual(patient.full_name, "Maya Haddad")
        self.assertEqual(patient.gender, "Female")
        self.assertEqual(patient.phone_number, "+1-555-0100")
        self.assertEqual(patient.medical_conditions_history, "None")
        self.assertEqual(patient.version, 1)

    def test_patient_national_id_or_passport_is_stored_as_string(self):
        patient = Patient.objects.create(
            first_name="Omar",
            last_name="Saleh",
            gender=Patient.Gender.MALE,
            national_id_or_passport="AB1234567",
        )

        patient.refresh_from_db()
        self.assertIsInstance(patient.national_id_or_passport, str)
        self.assertEqual(patient.national_id_or_passport, "AB1234567")

    def test_age_is_calculated_from_date_of_birth(self):
        today = timezone.localdate()
        dob = date(today.year - 30, today.month, min(today.day, 28))
        patient = Patient.objects.create(
            first_name="Age",
            last_name="Check",
            gender=Patient.Gender.FEMALE,
            date_of_birth=dob,
            national_id_or_passport="AGE-30",
        )

        self.assertEqual(PatientSerializer(patient).data["age"], 30)

    def test_age_is_null_when_date_of_birth_is_null(self):
        patient = Patient.objects.create(
            first_name="No",
            last_name="Dob",
            gender=Patient.Gender.MALE,
            date_of_birth=None,
            national_id_or_passport="NO-DOB",
        )

        self.assertIsNone(PatientSerializer(patient).data["age"])

    def test_version_defaults_to_one(self):
        patient = Patient.objects.create(
            first_name="Version",
            last_name="One",
            gender=Patient.Gender.FEMALE,
            national_id_or_passport="V-1",
        )

        self.assertEqual(patient.version, 1)


class PatientAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = User.objects.create_user(
            username="admin-patient@example.com",
            email="admin-patient@example.com",
            password="test-pass-123",
            full_name="Admin Patient",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.staff = User.objects.create_user(
            username="staff-patient@example.com",
            email="staff-patient@example.com",
            password="test-pass-123",
            full_name="Staff Patient",
            role=User.Role.STAFF,
            status=User.Status.ACTIVE,
        )
        self.doctor = User.objects.create_user(
            username="doctor-patient@example.com",
            email="doctor-patient@example.com",
            password="test-pass-123",
            full_name="Doctor Patient",
            role=User.Role.DOCTOR,
            status=User.Status.ACTIVE,
        )
        self.inactive = User.objects.create_user(
            username="inactive-patient@example.com",
            email="inactive-patient@example.com",
            password="test-pass-123",
            full_name="Inactive Patient",
            role=User.Role.STAFF,
            status=User.Status.INACTIVE,
            is_active=False,
        )
        self.patient = Patient.objects.create(
            first_name="Alice",
            last_name="Rivera",
            gender=Patient.Gender.FEMALE,
            date_of_birth=date(1990, 4, 15),
            phone_number="+1-555-0101",
            email="alice@example.com",
            national_id_or_passport="ALICE-001",
            medical_conditions_history="None",
            blood_group=Patient.BloodGroup.A_POSITIVE,
            insurance_info="Plan A",
            emergency_contact="+1-555-0110",
            address="1 River Road",
        )
        self.other_patient = Patient.objects.create(
            first_name="Basil",
            last_name="Kareem",
            gender=Patient.Gender.MALE,
            date_of_birth=date(1985, 8, 10),
            phone_number="+1-555-0202",
            email="basil@example.com",
            national_id_or_passport="BASIL-002",
            medical_conditions_history="Asthma",
            blood_group=Patient.BloodGroup.B_POSITIVE,
            insurance_info="Plan B",
            emergency_contact="+1-555-0220",
            address="2 Cedar Street",
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def valid_payload(self, **overrides):
        payload = {
            "firstName": "Nadia",
            "lastName": "Mansour",
            "gender": "Female",
            "dateOfBirth": "1995-03-12",
            "phoneNumber": "+1-555-0303",
            "email": "nadia@example.com",
            "nationalIdOrPassport": "NADIA-003",
            "medicalConditionsHistory": "None",
            "bloodGroup": "O+",
            "insuranceInfo": "Plan C",
            "emergencyContact": "+1-555-0330",
            "address": "3 Palm Avenue",
        }
        payload.update(overrides)
        return payload

    def test_anonymous_list_is_rejected(self):
        response = self.client.get("/api/patients/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list_and_retrieve_patients(self):
        self.authenticate(self.admin)

        list_response = self.client.get("/api/patients/")
        retrieve_response = self.client.get(f"/api/patients/{self.patient.id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data["id"], self.patient.id)

    def test_admin_cannot_create_patient(self):
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/patients/",
            self.valid_payload(nationalIdOrPassport="ADMIN-001"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_update_patient(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/patients/{self.patient.id}/",
            {"phoneNumber": "+1-555-9999", "version": self.patient.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_list_retrieve_create_and_update_patients(self):
        self.authenticate(self.staff)

        list_response = self.client.get("/api/patients/")
        retrieve_response = self.client.get(f"/api/patients/{self.patient.id}/")
        create_response = self.client.post(
            "/api/patients/",
            self.valid_payload(nationalIdOrPassport="STAFF-NEW"),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/patients/{self.patient.id}/",
            {"phoneNumber": "+1-555-7777", "version": self.patient.version},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["phoneNumber"], "+1-555-7777")

    def test_doctor_cannot_list_global_patients_in_phase_three(self):
        self.authenticate(self.doctor)

        response = self.client.get("/api/patients/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_retrieve_arbitrary_patient_in_phase_three(self):
        self.authenticate(self.doctor)

        response = self.client.get(f"/api/patients/{self.patient.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_user_is_rejected(self):
        self.authenticate(self.inactive)

        response = self.client.get("/api/patients/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_list_returns_source_aligned_camel_case_fields(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/patients/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data["results"][0]
        self.assertIn("firstName", result)
        self.assertIn("lastName", result)
        self.assertIn("fullName", result)
        self.assertIn("gender", result)
        self.assertIn("dateOfBirth", result)
        self.assertIn("phoneNumber", result)
        self.assertIn("nationalIdOrPassport", result)
        self.assertIn("medicalConditionsHistory", result)
        self.assertIn("bloodGroup", result)
        self.assertIn("insuranceInfo", result)
        self.assertIn("emergencyContact", result)
        self.assertIn("createdAt", result)
        self.assertIn("updatedAt", result)
        self.assertNotIn("sex", result)
        self.assertNotIn("phone", result)
        self.assertNotIn("medicalConditions", result)
        self.assertNotIn("first_name", result)
        self.assertNotIn("national_id_or_passport", result)

    def test_create_returns_patient_data_with_version(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/patients/",
            self.valid_payload(nationalIdOrPassport="CREATE-001"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["version"], 1)
        self.assertEqual(response.data["gender"], "Female")
        self.assertEqual(response.data["phoneNumber"], "+1-555-0303")

    def test_retrieve_returns_calculated_age(self):
        self.authenticate(self.staff)

        response = self.client.get(f"/api/patients/{self.patient.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["age"], Patient.objects.get(pk=self.patient.pk).age)

    def assert_search_finds_patient(self, search):
        response = self.client.get("/api/patients/", {"search": search})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {patient["id"] for patient in response.data["results"]}
        self.assertIn(self.patient.id, ids)

    def test_search_by_first_name_works(self):
        self.authenticate(self.staff)

        self.assert_search_finds_patient("Alice")

    def test_search_by_last_name_works(self):
        self.authenticate(self.staff)

        self.assert_search_finds_patient("Rivera")

    def test_search_by_phone_number_works(self):
        self.authenticate(self.staff)

        self.assert_search_finds_patient("0101")

    def test_search_by_email_works(self):
        self.authenticate(self.staff)

        self.assert_search_finds_patient("alice@example.com")

    def test_search_by_national_id_or_passport_works(self):
        self.authenticate(self.staff)

        self.assert_search_finds_patient("ALICE-001")

    def test_patch_with_correct_version_succeeds_and_increments_version(self):
        self.authenticate(self.staff)

        response = self.client.patch(
            f"/api/patients/{self.patient.id}/",
            {"phoneNumber": "+1-555-8888", "version": self.patient.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], 2)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.phone_number, "+1-555-8888")
        self.assertEqual(self.patient.version, 2)

    def test_patch_with_stale_version_returns_409(self):
        self.authenticate(self.staff)
        self.patient.version = 3
        self.patient.save()

        response = self.client.patch(
            f"/api/patients/{self.patient.id}/",
            {"phoneNumber": "+1-555-8888", "version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Version conflict")
        self.assertEqual(response.data["currentVersion"], 3)

    def test_patch_without_version_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.patch(
            f"/api/patients/{self.patient.id}/",
            {"phoneNumber": "+1-555-8888"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", response.data)

    def test_invalid_date_of_birth_returns_400(self):
        self.authenticate(self.staff)
        tomorrow = timezone.localdate() + timedelta(days=1)

        response = self.client.post(
            "/api/patients/",
            self.valid_payload(
                dateOfBirth=tomorrow.isoformat(),
                nationalIdOrPassport="FUTURE-DOB",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("dateOfBirth", response.data)

    def test_invalid_gender_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/patients/",
            self.valid_payload(gender="Unknown", nationalIdOrPassport="BAD-GENDER"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("gender", response.data)

    def test_invalid_blood_group_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/patients/",
            self.valid_payload(bloodGroup="X+", nationalIdOrPassport="BAD-BLOOD"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("bloodGroup", response.data)

    def test_health_endpoint_remains_public(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_auth_me_still_works(self):
        self.authenticate(self.staff)

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "staff-patient@example.com")

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
