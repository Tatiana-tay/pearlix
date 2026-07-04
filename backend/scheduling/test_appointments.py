from datetime import datetime, timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import ClinicSettings
from employees.models import EmployeeProfile
from patients.models import Patient

from .models import Appointment, AvailabilityException, WorkingShift


BASE_AT = datetime(2026, 7, 6, 9, 0, tzinfo=datetime_timezone.utc)


class AppointmentTestHelpers:
    def set_clinic(self, capacity=2):
        settings = ClinicSettings.get_solo()
        settings.clinic_timezone = "UTC"
        settings.max_simultaneous_appointments = capacity
        settings.save()
        return settings

    def make_user(self, role, email, *, user_status=None, is_staff=False, is_superuser=False):
        User = get_user_model()
        return User.objects.create_user(
            username=email,
            email=email,
            password="test-pass-123",
            full_name=email.split("@")[0].replace("-", " ").title(),
            role=role,
            status=user_status or User.Status.ACTIVE,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )

    def make_profile(self, role, email, specialty="Endodontics"):
        User = get_user_model()
        user = self.make_user(role, email)
        return EmployeeProfile.objects.create(
            user=user,
            specialty=specialty if role == User.Role.DOCTOR else "",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-3000",
        )

    def make_patient(self, suffix):
        return Patient.objects.create(
            first_name=f"Patient{suffix}",
            last_name="Appointment",
            gender=Patient.Gender.FEMALE,
            national_id_or_passport=f"appt-{suffix}",
        )

    def make_shift(self, profile, *, is_active=True):
        return WorkingShift.objects.create(
            employee_profile=profile,
            day_of_week=WorkingShift.DayOfWeek.MONDAY,
            start_time=datetime(2026, 1, 1, 9, 0).time(),
            end_time=datetime(2026, 1, 1, 17, 0).time(),
            is_active=is_active,
        )

    def make_appointment(
        self,
        patient,
        doctor_profile,
        *,
        start_at=BASE_AT,
        end_at=None,
        duration_minutes=60,
        status_value=None,
        **overrides,
    ):
        values = {
            "patient": patient,
            "doctor_profile": doctor_profile,
            "start_at": start_at,
            "end_at": end_at or start_at + timedelta(minutes=duration_minutes),
            "duration_minutes": duration_minutes,
            "visit_type": Appointment.VisitType.ROUTINE_CHECKUP,
            "notes": "",
        }
        if status_value:
            values["status"] = status_value
        values.update(overrides)
        return Appointment.objects.create(**values)


class AppointmentModelTests(AppointmentTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=2)

    def test_appointment_can_be_created_for_patient_and_doctor_profile(self):
        User = get_user_model()
        patient = self.make_patient("create")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "doctor-appt@example.com")
        self.make_shift(doctor_profile)

        appointment = self.make_appointment(patient, doctor_profile)

        self.assertEqual(appointment.patient, patient)
        self.assertEqual(appointment.doctor_profile, doctor_profile)

    def test_appointment_cannot_use_staff_profile_as_doctor(self):
        User = get_user_model()
        patient = self.make_patient("staff-doctor")
        staff_profile = self.make_profile(User.Role.STAFF, "staff-as-doctor@example.com")
        self.make_shift(staff_profile)

        with self.assertRaises(ValidationError):
            self.make_appointment(patient, staff_profile)

    def test_start_at_must_be_before_end_at(self):
        User = get_user_model()
        patient = self.make_patient("bad-time")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "bad-time-doctor@example.com")
        self.make_shift(doctor_profile)

        with self.assertRaises(ValidationError):
            self.make_appointment(
                patient,
                doctor_profile,
                end_at=BASE_AT,
                duration_minutes=0,
            )

    def test_duration_minutes_must_be_at_least_source_minimum(self):
        User = get_user_model()
        patient = self.make_patient("bad-duration")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "bad-duration@example.com")
        self.make_shift(doctor_profile)

        with self.assertRaises(ValidationError):
            self.make_appointment(
                patient,
                doctor_profile,
                duration_minutes=10,
                end_at=BASE_AT + timedelta(minutes=10),
            )

    def test_duration_minutes_must_match_interval(self):
        User = get_user_model()
        patient = self.make_patient("duration-mismatch")
        doctor_profile = self.make_profile(
            User.Role.DOCTOR,
            "duration-mismatch@example.com",
        )
        self.make_shift(doctor_profile)

        with self.assertRaises(ValidationError):
            self.make_appointment(
                patient,
                doctor_profile,
                duration_minutes=60,
                end_at=BASE_AT + timedelta(minutes=45),
            )

    def test_status_defaults_to_scheduled(self):
        User = get_user_model()
        patient = self.make_patient("default-status")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "default-status@example.com")
        self.make_shift(doctor_profile)

        appointment = self.make_appointment(patient, doctor_profile)

        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

    def test_status_enum_includes_postponed(self):
        status_values = {value for value, _ in Appointment.Status.choices}

        self.assertIn("Postponed", status_values)

    def test_model_has_no_due_or_due_amount_fields(self):
        field_names = {field.name for field in Appointment._meta.get_fields()}

        self.assertNotIn("due", field_names)
        self.assertNotIn("due_amount", field_names)
        self.assertNotIn("balance", field_names)

    def test_version_defaults_to_one(self):
        User = get_user_model()
        patient = self.make_patient("version")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "version-appt@example.com")
        self.make_shift(doctor_profile)

        appointment = self.make_appointment(patient, doctor_profile)

        self.assertEqual(appointment.version, 1)

    def test_appointment_inside_active_working_shift_is_allowed(self):
        User = get_user_model()
        patient = self.make_patient("inside-shift")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "inside-shift@example.com")
        self.make_shift(doctor_profile)

        appointment = self.make_appointment(patient, doctor_profile)

        self.assertEqual(appointment.start_at, BASE_AT)

    def test_appointment_outside_working_shift_is_rejected(self):
        User = get_user_model()
        patient = self.make_patient("outside-shift")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "outside-shift@example.com")
        self.make_shift(doctor_profile)

        with self.assertRaises(ValidationError):
            self.make_appointment(
                patient,
                doctor_profile,
                start_at=BASE_AT + timedelta(hours=9),
            )

    def test_appointment_partially_outside_working_shift_is_rejected(self):
        User = get_user_model()
        patient = self.make_patient("partial-shift")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "partial-shift@example.com")
        self.make_shift(doctor_profile)

        with self.assertRaises(ValidationError):
            self.make_appointment(
                patient,
                doctor_profile,
                start_at=BASE_AT + timedelta(hours=7, minutes=30),
                end_at=BASE_AT + timedelta(hours=8, minutes=30),
                duration_minutes=60,
            )

    def test_inactive_working_shift_does_not_cover_appointment(self):
        User = get_user_model()
        patient = self.make_patient("inactive-shift")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "inactive-shift@example.com")
        self.make_shift(doctor_profile, is_active=False)

        with self.assertRaises(ValidationError):
            self.make_appointment(patient, doctor_profile)

    def test_active_availability_exception_rejects_appointment(self):
        User = get_user_model()
        patient = self.make_patient("leave-block")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "leave-block@example.com")
        self.make_shift(doctor_profile)
        AvailabilityException.objects.create(
            employee_profile=doctor_profile,
            start_at=BASE_AT + timedelta(minutes=15),
            end_at=BASE_AT + timedelta(minutes=45),
            reason=AvailabilityException.Reason.LEAVE,
        )

        with self.assertRaises(ValidationError):
            self.make_appointment(patient, doctor_profile)

    def test_cancelled_availability_exception_does_not_reject_appointment(self):
        User = get_user_model()
        patient = self.make_patient("cancelled-leave")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "cancelled-leave@example.com")
        self.make_shift(doctor_profile)
        AvailabilityException.objects.create(
            employee_profile=doctor_profile,
            start_at=BASE_AT + timedelta(minutes=15),
            end_at=BASE_AT + timedelta(minutes=45),
            reason=AvailabilityException.Reason.LEAVE,
            status=AvailabilityException.Status.CANCELLED,
        )

        appointment = self.make_appointment(patient, doctor_profile)

        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

    def test_same_doctor_overlapping_blocking_appointment_is_rejected(self):
        User = get_user_model()
        patient = self.make_patient("same-doctor-overlap")
        other_patient = self.make_patient("same-doctor-overlap-2")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "same-doctor@example.com")
        self.make_shift(doctor_profile)
        self.make_appointment(patient, doctor_profile)

        with self.assertRaises(ValidationError):
            self.make_appointment(
                other_patient,
                doctor_profile,
                start_at=BASE_AT + timedelta(minutes=30),
            )

    def test_same_doctor_boundary_touching_appointments_are_allowed(self):
        User = get_user_model()
        patient = self.make_patient("boundary-1")
        other_patient = self.make_patient("boundary-2")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "boundary-doctor@example.com")
        self.make_shift(doctor_profile)
        self.make_appointment(patient, doctor_profile)

        appointment = self.make_appointment(
            other_patient,
            doctor_profile,
            start_at=BASE_AT + timedelta(minutes=60),
        )

        self.assertEqual(appointment.start_at, BASE_AT + timedelta(minutes=60))

    def test_different_doctor_overlap_allowed_when_capacity_allows(self):
        User = get_user_model()
        patient = self.make_patient("different-doctor-1")
        other_patient = self.make_patient("different-doctor-2")
        first_doctor = self.make_profile(User.Role.DOCTOR, "first-capacity@example.com")
        second_doctor = self.make_profile(User.Role.DOCTOR, "second-capacity@example.com")
        self.make_shift(first_doctor)
        self.make_shift(second_doctor)
        self.make_appointment(patient, first_doctor)

        appointment = self.make_appointment(
            other_patient,
            second_doctor,
            start_at=BASE_AT + timedelta(minutes=30),
        )

        self.assertEqual(appointment.doctor_profile, second_doctor)

    def test_different_doctor_overlap_rejected_when_capacity_exceeded(self):
        self.set_clinic(capacity=1)
        User = get_user_model()
        patient = self.make_patient("capacity-1")
        other_patient = self.make_patient("capacity-2")
        first_doctor = self.make_profile(User.Role.DOCTOR, "capacity-one@example.com")
        second_doctor = self.make_profile(User.Role.DOCTOR, "capacity-two@example.com")
        self.make_shift(first_doctor)
        self.make_shift(second_doctor)
        self.make_appointment(patient, first_doctor)

        with self.assertRaises(ValidationError):
            self.make_appointment(
                other_patient,
                second_doctor,
                start_at=BASE_AT + timedelta(minutes=30),
            )

    def test_completed_cancelled_no_show_do_not_block_overlap_or_capacity(self):
        self.set_clinic(capacity=1)
        User = get_user_model()
        doctor_profile = self.make_profile(User.Role.DOCTOR, "terminal-doctor@example.com")
        self.make_shift(doctor_profile)
        for suffix, status_value in (
            ("completed", Appointment.Status.COMPLETED),
            ("cancelled", Appointment.Status.CANCELLED),
            ("no-show", Appointment.Status.NO_SHOW),
            ("postponed", Appointment.Status.POSTPONED),
        ):
            self.make_appointment(
                self.make_patient(suffix),
                doctor_profile,
                status_value=status_value,
            )

        appointment = self.make_appointment(self.make_patient("new"), doctor_profile)

        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

    def test_same_doctor_overlapping_postponed_appointment_does_not_block(self):
        User = get_user_model()
        postponed_patient = self.make_patient("postponed-overlap")
        new_patient = self.make_patient("postponed-new")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "postponed-doctor@example.com")
        self.make_shift(doctor_profile)
        self.make_appointment(
            postponed_patient,
            doctor_profile,
            status_value=Appointment.Status.POSTPONED,
        )

        appointment = self.make_appointment(
            new_patient,
            doctor_profile,
            start_at=BASE_AT + timedelta(minutes=30),
        )

        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

    def test_postponed_appointment_does_not_count_toward_capacity(self):
        self.set_clinic(capacity=1)
        User = get_user_model()
        postponed_patient = self.make_patient("postponed-capacity")
        new_patient = self.make_patient("postponed-capacity-new")
        first_doctor = self.make_profile(User.Role.DOCTOR, "postponed-capacity-one@example.com")
        second_doctor = self.make_profile(User.Role.DOCTOR, "postponed-capacity-two@example.com")
        self.make_shift(first_doctor)
        self.make_shift(second_doctor)
        self.make_appointment(
            postponed_patient,
            first_doctor,
            status_value=Appointment.Status.POSTPONED,
        )

        appointment = self.make_appointment(
            new_patient,
            second_doctor,
            start_at=BASE_AT + timedelta(minutes=30),
        )

        self.assertEqual(appointment.doctor_profile, second_doctor)

    def test_needs_reschedule_still_blocks_same_doctor_overlap(self):
        User = get_user_model()
        first_patient = self.make_patient("needs-reschedule")
        second_patient = self.make_patient("needs-reschedule-new")
        doctor_profile = self.make_profile(User.Role.DOCTOR, "needs-reschedule@example.com")
        self.make_shift(doctor_profile)
        self.make_appointment(
            first_patient,
            doctor_profile,
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )

        with self.assertRaises(ValidationError):
            self.make_appointment(
                second_patient,
                doctor_profile,
                start_at=BASE_AT + timedelta(minutes=30),
            )


class AppointmentAPITests(AppointmentTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=2)
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-appointment@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-appointment@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-appointment@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-appointment@example.com",
        )
        self.inactive = self.make_user(
            User.Role.STAFF,
            "inactive-appointment@example.com",
            user_status=User.Status.INACTIVE,
        )
        self.patient = self.make_patient("api")
        self.other_patient = self.make_patient("api-other")
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-3100",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-3101",
        )
        self.staff_profile = EmployeeProfile.objects.create(
            user=self.staff,
            specialty="",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-3102",
        )
        self.make_shift(self.doctor_profile)
        self.make_shift(self.other_doctor_profile)
        self.appointment = self.make_appointment(self.patient, self.doctor_profile)

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def iso(self, value):
        return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")

    def payload(self, profile=None, patient=None, start_at=None, duration_minutes=60, **overrides):
        start_at = start_at or BASE_AT + timedelta(days=7)
        payload = {
            "patientId": (patient or self.patient).id,
            "doctorProfileId": (profile or self.doctor_profile).id,
            "startAt": self.iso(start_at),
            "endAt": self.iso(start_at + timedelta(minutes=duration_minutes)),
            "durationMinutes": duration_minutes,
            "visitType": "Routine Checkup",
            "notes": "API appointment",
        }
        payload.update(overrides)
        return payload

    def test_anonymous_list_is_rejected(self):
        response = self.client.get("/api/appointments/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_is_rejected(self):
        self.authenticate(self.inactive)

        response = self.client.get("/api/appointments/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_staff_can_list_retrieve_create_and_update(self):
        self.authenticate(self.staff)

        list_response = self.client.get("/api/appointments/")
        retrieve_response = self.client.get(f"/api/appointments/{self.appointment.id}/")
        create_response = self.client.post(
            "/api/appointments/",
            self.payload(start_at=BASE_AT + timedelta(days=7, hours=1)),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"notes": "Updated", "version": self.appointment.version},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["version"], 2)

    def test_admin_can_list_retrieve_but_cannot_create_or_update(self):
        self.authenticate(self.admin)

        list_response = self.client.get("/api/appointments/")
        retrieve_response = self.client.get(f"/api/appointments/{self.appointment.id}/")
        create_response = self.client.post(
            "/api/appointments/",
            self.payload(),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"notes": "Nope", "version": self.appointment.version},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_list_and_retrieve_own_appointments_only(self):
        other_appointment = self.make_appointment(
            self.other_patient,
            self.other_doctor_profile,
            start_at=BASE_AT + timedelta(hours=2),
        )
        self.authenticate(self.doctor)

        list_response = self.client.get("/api/appointments/")
        filtered_response = self.client.get(
            "/api/appointments/",
            {"doctorProfileId": self.other_doctor_profile.id},
        )
        retrieve_own_response = self.client.get(
            f"/api/appointments/{self.appointment.id}/"
        )
        retrieve_other_response = self.client.get(
            f"/api/appointments/{other_appointment.id}/"
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [self.appointment.id])
        self.assertEqual(filtered_response.data["results"], [])
        self.assertEqual(retrieve_own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_other_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_create_or_update(self):
        self.authenticate(self.doctor)

        create_response = self.client.post(
            "/api/appointments/",
            self.payload(),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"notes": "Nope", "version": self.appointment.version},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_appointment_returns_camel_case_fields_and_default_status(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(start_at=BASE_AT + timedelta(days=7, hours=1)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "Scheduled")
        self.assertIn("patientId", response.data)
        self.assertIn("patientName", response.data)
        self.assertIn("doctorProfileId", response.data)
        self.assertIn("doctorName", response.data)
        self.assertIn("startAt", response.data)
        self.assertIn("durationMinutes", response.data)
        self.assertIn("visitType", response.data)
        self.assertNotIn("patient_id", response.data)
        for forbidden in ("due", "dueAmount", "balance", "invoice", "payment"):
            self.assertNotIn(forbidden, response.data)

    def test_create_appointment_rejects_status_field(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(status="Arrived"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_list_supports_filters(self):
        self.authenticate(self.staff)

        patient_response = self.client.get(
            "/api/appointments/",
            {"patientId": self.patient.id},
        )
        doctor_response = self.client.get(
            "/api/appointments/",
            {"doctorProfileId": self.doctor_profile.id},
        )
        status_response = self.client.get("/api/appointments/", {"status": "Scheduled"})
        window_response = self.client.get(
            "/api/appointments/",
            {
                "from": self.iso(BASE_AT + timedelta(minutes=15)),
                "to": self.iso(BASE_AT + timedelta(minutes=45)),
            },
        )

        self.assertEqual(patient_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in patient_response.data["results"]], [self.appointment.id])
        self.assertEqual([item["id"] for item in doctor_response.data["results"]], [self.appointment.id])
        self.assertEqual([item["id"] for item in status_response.data["results"]], [self.appointment.id])
        self.assertEqual([item["id"] for item in window_response.data["results"]], [self.appointment.id])

    def test_patch_with_correct_version_succeeds_and_increments_version(self):
        self.authenticate(self.staff)

        response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"notes": "Updated notes", "version": self.appointment.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], 2)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.notes, "Updated notes")

    def test_patch_with_stale_version_returns_409(self):
        self.authenticate(self.staff)
        self.appointment.version = 3
        self.appointment.save()

        response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"notes": "Stale", "version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Version conflict")
        self.assertEqual(response.data["currentVersion"], 3)

    def test_patch_without_version_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"notes": "Missing version"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", response.data)

    def test_invalid_datetime_interval_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(
                start_at=BASE_AT + timedelta(days=7, hours=3),
                endAt=self.iso(BASE_AT + timedelta(days=7, hours=2)),
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_at", response.data)

    def test_invalid_doctor_profile_role_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(profile=self.staff_profile),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("doctor_profile", response.data)

    def test_shift_coverage_failure_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(start_at=BASE_AT + timedelta(days=7, hours=9)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_leave_conflict_returns_400(self):
        self.authenticate(self.staff)
        leave_start = BASE_AT + timedelta(days=7, hours=1)
        AvailabilityException.objects.create(
            employee_profile=self.doctor_profile,
            start_at=leave_start,
            end_at=leave_start + timedelta(hours=1),
            reason=AvailabilityException.Reason.LEAVE,
        )

        response = self.client.post(
            "/api/appointments/",
            self.payload(start_at=leave_start),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_same_doctor_overlap_returns_400(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(start_at=BASE_AT + timedelta(minutes=30)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_different_doctor_overlap_allowed_when_capacity_allows(self):
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(
                profile=self.other_doctor_profile,
                patient=self.other_patient,
                start_at=BASE_AT + timedelta(minutes=30),
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["doctorProfileId"], self.other_doctor_profile.id)

    def test_capacity_exceeded_returns_400(self):
        self.set_clinic(capacity=1)
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/appointments/",
            self.payload(
                profile=self.other_doctor_profile,
                patient=self.other_patient,
                start_at=BASE_AT + timedelta(minutes=30),
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_update_ignores_itself_for_overlap_and_capacity_checks(self):
        self.set_clinic(capacity=1)
        self.authenticate(self.staff)

        response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {
                "notes": "Self update",
                "version": self.appointment.version,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], 2)

    def test_regression_endpoints_still_work(self):
        self.authenticate(self.staff)

        health = self.client.get("/api/health/")
        auth_me = self.client.get("/api/auth/me/")
        roles = self.client.get("/api/auth/roles/")
        clinic = self.client.get("/api/clinic/settings/")
        patients = self.client.get("/api/patients/")
        profiles = self.client.get("/api/employee-profiles/")
        shifts = self.client.get("/api/working-shifts/")
        exceptions = self.client.get("/api/availability-exceptions/")

        self.assertEqual(health.status_code, status.HTTP_200_OK)
        self.assertEqual(auth_me.status_code, status.HTTP_200_OK)
        self.assertEqual(roles.status_code, status.HTTP_200_OK)
        self.assertEqual(clinic.status_code, status.HTTP_200_OK)
        self.assertEqual(patients.status_code, status.HTTP_200_OK)
        self.assertEqual(profiles.status_code, status.HTTP_200_OK)
        self.assertEqual(shifts.status_code, status.HTTP_200_OK)
        self.assertEqual(exceptions.status_code, status.HTTP_200_OK)
