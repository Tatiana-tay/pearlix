from datetime import timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from employees.models import EmployeeProfile
from scheduling.models import Appointment, AppointmentChangeLog
from scheduling.test_appointments import AppointmentTestHelpers, BASE_AT

from .models import Visit


class VisitTestHelpers(AppointmentTestHelpers):
    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def iso(self, value):
        return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")

    def make_visit_appointment(
        self,
        suffix,
        *,
        doctor_profile=None,
        patient=None,
        status_value=Appointment.Status.CHECKED_IN,
        start_at=BASE_AT,
    ):
        return self.make_appointment(
            patient or self.make_patient(suffix),
            doctor_profile or self.doctor_profile,
            status_value=status_value,
            start_at=start_at,
        )

    def make_visit(self, appointment, *, status_value=Visit.Status.ACTIVE, **overrides):
        values = {
            "appointment": appointment,
            "patient": appointment.patient,
            "doctor_profile": appointment.doctor_profile,
            "status": status_value,
            "started_at": overrides.pop("started_at", timezone.now()),
        }
        if status_value == Visit.Status.COMPLETED:
            values["completed_at"] = overrides.pop("completed_at", timezone.now())
        values.update(overrides)
        return Visit.objects.create(**values)


class VisitModelTests(VisitTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=2)
        User = get_user_model()
        self.User = User
        self.doctor_profile = self.make_profile(User.Role.DOCTOR, "visit-model-doctor@example.com")
        self.staff_profile = self.make_profile(User.Role.STAFF, "visit-model-staff@example.com")
        self.make_shift(self.doctor_profile)

    def test_visit_can_be_created_for_appointment_doctor_and_patient(self):
        appointment = self.make_visit_appointment("model-create")

        visit = self.make_visit(appointment)

        self.assertEqual(visit.appointment, appointment)
        self.assertEqual(visit.doctor_profile, appointment.doctor_profile)
        self.assertEqual(visit.patient, appointment.patient)

    def test_visit_cannot_use_staff_employee_profile_as_doctor(self):
        appointment = self.make_visit_appointment("staff-profile")

        with self.assertRaises(ValidationError):
            self.make_visit(appointment, doctor_profile=self.staff_profile)

    def test_visit_doctor_and_patient_must_match_appointment(self):
        other_doctor = self.make_profile(self.User.Role.DOCTOR, "visit-other-doctor@example.com")
        self.make_shift(other_doctor)
        other_patient = self.make_patient("wrong-patient")
        appointment = self.make_visit_appointment("matching")

        with self.assertRaises(ValidationError):
            self.make_visit(appointment, doctor_profile=other_doctor)
        with self.assertRaises(ValidationError):
            self.make_visit(appointment, patient=other_patient)

    def test_one_appointment_cannot_have_two_visits(self):
        appointment = self.make_visit_appointment("one-to-one")
        self.make_visit(appointment)

        with self.assertRaises(ValidationError):
            self.make_visit(appointment)

    def test_visit_defaults_and_required_completion_timestamp(self):
        appointment = self.make_visit_appointment("defaults")

        visit = self.make_visit(appointment)

        self.assertEqual(visit.status, Visit.Status.ACTIVE)
        self.assertIsNotNone(visit.started_at)
        self.assertIsNone(visit.completed_at)
        self.assertEqual(visit.version, 1)

        with self.assertRaises(ValidationError):
            self.make_visit(
                self.make_visit_appointment("bad-complete", start_at=BASE_AT + timedelta(hours=1)),
                status_value=Visit.Status.COMPLETED,
                completed_at=None,
            )


class VisitAPITests(VisitTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=2)
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-visits@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-visits@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-visits@example.com")
        self.other_doctor = self.make_user(User.Role.DOCTOR, "other-doctor-visits@example.com")
        self.inactive = self.make_user(
            User.Role.DOCTOR,
            "inactive-visits@example.com",
            user_status=User.Status.INACTIVE,
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-5100",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-5101",
        )
        self.inactive_doctor_profile = EmployeeProfile.objects.create(
            user=self.inactive,
            specialty="Periodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-5102",
        )
        self.make_shift(self.doctor_profile)
        self.make_shift(self.other_doctor_profile)

    def start_visit(self, appointment, *, user=None, version=None, reason="Begin visit"):
        self.authenticate(user or self.doctor)
        return self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {"version": version if version is not None else appointment.version, "reason": reason},
            format="json",
        )

    def complete_visit(self, visit, *, user=None, version=None, **overrides):
        self.authenticate(user or self.doctor)
        payload = {
            "version": version if version is not None else visit.version,
            "subjectiveNotes": "Patient reports sensitivity",
            "objectiveNotes": "No swelling observed",
            "assessmentNotes": "Routine review",
            "planNotes": "Follow up if symptoms persist",
            "generalNotes": "Completed cleanly",
            "reason": "Visit complete",
        }
        payload.update(overrides)
        return self.client.post(
            f"/api/visits/{visit.id}/complete/",
            payload,
            format="json",
        )

    def test_doctor_can_start_own_checked_in_appointment(self):
        appointment = self.make_visit_appointment("start-own")

        response = self.start_visit(appointment)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["appointment"]["status"], Appointment.Status.IN_VISIT)
        self.assertEqual(response.data["appointment"]["version"], 2)
        self.assertEqual(response.data["visit"]["status"], Visit.Status.ACTIVE)
        self.assertEqual(response.data["visit"]["appointmentId"], appointment.id)
        appointment.refresh_from_db()
        visit = Visit.objects.get(appointment=appointment)
        self.assertEqual(appointment.status, Appointment.Status.IN_VISIT)
        self.assertEqual(visit.patient, appointment.patient)
        self.assertEqual(visit.doctor_profile, appointment.doctor_profile)
        log = AppointmentChangeLog.objects.get(appointment=appointment)
        self.assertEqual(log.previous_status, Appointment.Status.CHECKED_IN)
        self.assertEqual(log.new_status, Appointment.Status.IN_VISIT)
        self.assertEqual(log.changed_by, self.doctor)
        self.assertEqual(log.metadata["visitId"], visit.id)

    def test_start_visit_response_uses_camel_case_and_omits_out_of_scope_fields(self):
        appointment = self.make_visit_appointment("response-shape")

        response = self.start_visit(appointment)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        visit_data = response.data["visit"]
        for field in (
            "appointmentId",
            "patientId",
            "patientName",
            "doctorProfileId",
            "doctorName",
            "subjectiveNotes",
            "objectiveNotes",
            "assessmentNotes",
            "planNotes",
            "generalNotes",
            "startedAt",
            "completedAt",
            "createdAt",
            "updatedAt",
        ):
            self.assertIn(field, visit_data)
        for field in (
            "due",
            "dueAmount",
            "balance",
            "invoice",
            "payment",
            "paidAmount",
            "remainingBalance",
            "aiDiagnosis",
            "aiResult",
            "xrayUrl",
        ):
            self.assertNotIn(field, visit_data)
            self.assertNotIn(field, response.data["appointment"])

    def test_start_visit_requires_current_appointment_version(self):
        appointment = self.make_visit_appointment("version-start")
        Appointment.objects.filter(pk=appointment.pk).update(version=3)
        self.authenticate(self.doctor)

        missing_response = self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {},
            format="json",
        )
        stale_response = self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {"version": 1},
            format="json",
        )

        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", missing_response.data)
        self.assertEqual(stale_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(stale_response.data["detail"], "Version conflict")
        self.assertEqual(stale_response.data["currentVersion"], 3)

    def test_doctor_cannot_start_other_doctor_or_non_checked_in_appointments(self):
        other_appointment = self.make_visit_appointment(
            "other-start",
            doctor_profile=self.other_doctor_profile,
        )
        self.authenticate(self.doctor)
        other_response = self.client.post(
            f"/api/appointments/{other_appointment.id}/start-visit/",
            {"version": other_appointment.version},
            format="json",
        )
        self.assertEqual(other_response.status_code, status.HTTP_403_FORBIDDEN)

        for index, appointment_status in enumerate(
            (
                Appointment.Status.SCHEDULED,
                Appointment.Status.ARRIVED,
                Appointment.Status.IN_VISIT,
                Appointment.Status.COMPLETED,
                Appointment.Status.CANCELLED,
                Appointment.Status.NO_SHOW,
                Appointment.Status.POSTPONED,
                Appointment.Status.NEEDS_RESCHEDULE,
            )
        ):
            appointment = self.make_visit_appointment(
                f"bad-start-{index}",
                status_value=appointment_status,
                start_at=BASE_AT + timedelta(hours=index),
            )
            response = self.client.post(
                f"/api/appointments/{appointment.id}/start-visit/",
                {"version": appointment.version},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_staff_admin_anonymous_and_inactive_users_cannot_start_visit(self):
        appointment = self.make_visit_appointment("start-permissions")

        anonymous_response = self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {"version": appointment.version},
            format="json",
        )
        self.authenticate(self.staff)
        staff_response = self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {"version": appointment.version},
            format="json",
        )
        self.authenticate(self.admin)
        admin_response = self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {"version": appointment.version},
            format="json",
        )
        self.authenticate(self.inactive)
        inactive_response = self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {"version": appointment.version},
            format="json",
        )

        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(staff_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            inactive_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_starting_same_appointment_twice_and_second_active_visit_are_rejected(self):
        first = self.make_visit_appointment("first-active")
        second = self.make_visit_appointment("second-active", start_at=BASE_AT + timedelta(hours=1))

        first_response = self.start_visit(first)
        first.refresh_from_db()
        second_response = self.start_visit(second)
        duplicate_response = self.client.post(
            f"/api/appointments/{first.id}/start-visit/",
            {"version": first.version},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_can_start_another_visit_after_previous_completed(self):
        first = self.make_visit_appointment("complete-before-next")
        second = self.make_visit_appointment("next-after-complete", start_at=BASE_AT + timedelta(hours=1))
        start_response = self.start_visit(first)
        visit = Visit.objects.get(id=start_response.data["visit"]["id"])
        complete_response = self.complete_visit(visit)

        second_response = self.start_visit(second)

        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

    def test_doctor_can_patch_own_active_visit_notes_with_version(self):
        appointment = self.make_visit_appointment("patch-notes")
        start_response = self.start_visit(appointment)
        visit_id = start_response.data["visit"]["id"]

        response = self.client.patch(
            f"/api/visits/{visit_id}/",
            {
                "version": 1,
                "subjectiveNotes": "Updated subjective",
                "objectiveNotes": "Updated objective",
                "assessmentNotes": "Updated assessment",
                "planNotes": "Updated plan",
                "generalNotes": "Updated general",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], 2)
        self.assertEqual(response.data["subjectiveNotes"], "Updated subjective")
        self.assertEqual(response.data["objectiveNotes"], "Updated objective")
        self.assertEqual(response.data["assessmentNotes"], "Updated assessment")
        self.assertEqual(response.data["planNotes"], "Updated plan")
        self.assertEqual(response.data["generalNotes"], "Updated general")

    def test_patch_notes_requires_version_and_rejects_stale_or_completed(self):
        appointment = self.make_visit_appointment("patch-errors")
        start_response = self.start_visit(appointment)
        visit = Visit.objects.get(id=start_response.data["visit"]["id"])

        missing_response = self.client.patch(
            f"/api/visits/{visit.id}/",
            {"generalNotes": "Missing version"},
            format="json",
        )
        Visit.objects.filter(pk=visit.pk).update(version=4)
        stale_response = self.client.patch(
            f"/api/visits/{visit.id}/",
            {"generalNotes": "Stale", "version": 1},
            format="json",
        )
        Visit.objects.filter(pk=visit.pk).update(version=1)
        complete_response = self.complete_visit(visit, version=1)
        completed_patch_response = self.client.patch(
            f"/api/visits/{visit.id}/",
            {"generalNotes": "Too late", "version": complete_response.data["visit"]["version"]},
            format="json",
        )

        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", missing_response.data)
        self.assertEqual(stale_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(stale_response.data["currentVersion"], 4)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(completed_patch_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_staff_and_admin_note_update_permissions(self):
        own = self.make_visit_appointment("own-patch")
        other = self.make_visit_appointment(
            "other-patch",
            doctor_profile=self.other_doctor_profile,
            start_at=BASE_AT + timedelta(hours=1),
        )
        own_visit = self.make_visit(own)
        other_visit = self.make_visit(other)

        self.authenticate(self.doctor)
        other_doctor_response = self.client.patch(
            f"/api/visits/{other_visit.id}/",
            {"version": other_visit.version, "generalNotes": "Nope"},
            format="json",
        )
        self.authenticate(self.staff)
        staff_response = self.client.patch(
            f"/api/visits/{own_visit.id}/",
            {"version": own_visit.version, "generalNotes": "Nope"},
            format="json",
        )
        self.authenticate(self.admin)
        admin_response = self.client.patch(
            f"/api/visits/{own_visit.id}/",
            {"version": own_visit.version, "generalNotes": "Nope"},
            format="json",
        )

        self.assertEqual(other_doctor_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_complete_own_active_visit(self):
        appointment = self.make_visit_appointment("complete-own")
        start_response = self.start_visit(appointment)
        visit = Visit.objects.get(id=start_response.data["visit"]["id"])

        response = self.complete_visit(visit)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["visit"]["status"], Visit.Status.COMPLETED)
        self.assertIsNotNone(response.data["visit"]["completedAt"])
        self.assertEqual(response.data["visit"]["version"], 2)
        self.assertEqual(response.data["appointment"]["status"], Appointment.Status.COMPLETED)
        self.assertEqual(response.data["appointment"]["version"], 3)
        visit.refresh_from_db()
        appointment.refresh_from_db()
        self.assertEqual(visit.status, Visit.Status.COMPLETED)
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)
        log = AppointmentChangeLog.objects.filter(
            appointment=appointment,
            new_status=Appointment.Status.COMPLETED,
        ).get()
        self.assertEqual(log.previous_status, Appointment.Status.IN_VISIT)
        self.assertEqual(log.changed_by, self.doctor)
        self.assertEqual(log.metadata["visitId"], visit.id)

    def test_complete_requires_version_and_rejects_stale_completed_or_bad_appointment_state(self):
        appointment = self.make_visit_appointment("complete-errors")
        start_response = self.start_visit(appointment)
        visit = Visit.objects.get(id=start_response.data["visit"]["id"])

        missing_response = self.client.post(
            f"/api/visits/{visit.id}/complete/",
            {},
            format="json",
        )
        Visit.objects.filter(pk=visit.pk).update(version=3)
        stale_response = self.complete_visit(visit, version=1)
        Visit.objects.filter(pk=visit.pk).update(version=1)
        complete_response = self.complete_visit(visit, version=1)
        completed_again_response = self.client.post(
            f"/api/visits/{visit.id}/complete/",
            {"version": complete_response.data["visit"]["version"]},
            format="json",
        )

        bad_state_appointment = self.make_visit_appointment(
            "bad-appointment-state",
            start_at=BASE_AT + timedelta(hours=1),
        )
        bad_state_visit = self.make_visit(bad_state_appointment)
        bad_state_response = self.complete_visit(
            bad_state_visit,
            version=bad_state_visit.version,
        )

        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", missing_response.data)
        self.assertEqual(stale_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(stale_response.data["currentVersion"], 3)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(completed_again_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad_state_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_permissions_reject_other_doctor_staff_and_admin(self):
        own_appointment = self.make_visit_appointment("complete-permissions")
        own_visit = self.make_visit(own_appointment)
        Appointment.objects.filter(pk=own_appointment.pk).update(status=Appointment.Status.IN_VISIT)

        other_appointment = self.make_visit_appointment(
            "other-complete",
            doctor_profile=self.other_doctor_profile,
            start_at=BASE_AT + timedelta(hours=1),
        )
        other_visit = self.make_visit(other_appointment)
        Appointment.objects.filter(pk=other_appointment.pk).update(status=Appointment.Status.IN_VISIT)

        other_doctor_response = self.complete_visit(other_visit, user=self.doctor)
        staff_response = self.complete_visit(own_visit, user=self.staff)
        admin_response = self.complete_visit(own_visit, user=self.admin)

        self.assertEqual(other_doctor_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_active_visit_endpoint_returns_own_active_visit_or_404(self):
        appointment = self.make_visit_appointment("active-endpoint")
        start_response = self.start_visit(appointment)
        visit_id = start_response.data["visit"]["id"]

        active_response = self.client.get("/api/visits/active/")
        active_by_appointment_response = self.client.get(
            "/api/visits/active/",
            {"appointmentId": appointment.id},
        )
        self.complete_visit(Visit.objects.get(id=visit_id))
        no_active_response = self.client.get("/api/visits/active/")
        self.authenticate(self.staff)
        staff_response = self.client.get("/api/visits/active/")
        self.authenticate(self.admin)
        admin_response = self.client.get("/api/visits/active/")

        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        self.assertEqual(active_response.data["id"], visit_id)
        self.assertEqual(active_by_appointment_response.status_code, status.HTTP_200_OK)
        self.assertEqual(active_by_appointment_response.data["id"], visit_id)
        self.assertEqual(no_active_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(staff_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_visit_list_retrieve_and_filters_follow_role_scope(self):
        own_appointment = self.make_visit_appointment("list-own")
        own_visit = self.make_visit(own_appointment)
        other_appointment = self.make_visit_appointment(
            "list-other",
            doctor_profile=self.other_doctor_profile,
            start_at=BASE_AT + timedelta(hours=1),
        )
        other_visit = self.make_visit(other_appointment)

        self.authenticate(self.doctor)
        doctor_list = self.client.get("/api/visits/")
        doctor_other_filter = self.client.get(
            "/api/visits/",
            {"doctorProfileId": self.other_doctor_profile.id},
        )
        doctor_own_retrieve = self.client.get(f"/api/visits/{own_visit.id}/")
        doctor_other_retrieve = self.client.get(f"/api/visits/{other_visit.id}/")

        self.authenticate(self.staff)
        staff_list = self.client.get("/api/visits/", {"patientId": own_appointment.patient_id})
        staff_status = self.client.get("/api/visits/", {"status": Visit.Status.ACTIVE})
        staff_appointment = self.client.get(
            "/api/visits/",
            {"appointmentId": own_appointment.id},
        )
        staff_range = self.client.get(
            "/api/visits/",
            {
                "from": self.iso(timezone.now() - timedelta(minutes=10)),
                "to": self.iso(timezone.now() + timedelta(minutes=10)),
            },
        )

        self.authenticate(self.admin)
        admin_retrieve = self.client.get(f"/api/visits/{other_visit.id}/")

        self.assertEqual(doctor_list.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in doctor_list.data["results"]}, {own_visit.id})
        self.assertEqual(doctor_other_filter.data["results"], [])
        self.assertEqual(doctor_own_retrieve.status_code, status.HTTP_200_OK)
        self.assertEqual(doctor_other_retrieve.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_list.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in staff_list.data["results"]], [own_visit.id])
        self.assertEqual(staff_status.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in staff_status.data["results"]}, {own_visit.id, other_visit.id})
        self.assertEqual([item["id"] for item in staff_appointment.data["results"]], [own_visit.id])
        self.assertEqual(staff_range.status_code, status.HTTP_200_OK)
        self.assertTrue(staff_range.data["results"])
        self.assertEqual(admin_retrieve.status_code, status.HTTP_200_OK)

    def test_visit_endpoints_reject_anonymous_and_inactive_users(self):
        response = self.client.get("/api/visits/")
        self.authenticate(self.inactive)
        inactive_response = self.client.get("/api/visits/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(
            inactive_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_visits_start_alias_works_with_appointment_id(self):
        appointment = self.make_visit_appointment("start-alias")
        self.authenticate(self.doctor)

        response = self.client.post(
            "/api/visits/start/",
            {"appointmentId": appointment.id, "version": appointment.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["appointment"]["status"], Appointment.Status.IN_VISIT)

    def test_regression_core_endpoints_and_phase8_workflow_still_work(self):
        appointment = self.make_visit_appointment(
            "phase8-still-works",
            status_value=Appointment.Status.SCHEDULED,
        )
        self.authenticate(self.staff)

        responses = (
            self.client.get("/api/health/"),
            self.client.get("/api/auth/me/"),
            self.client.get("/api/auth/roles/"),
            self.client.get("/api/clinic/settings/"),
            self.client.get("/api/patients/"),
            self.client.get("/api/employee-profiles/"),
            self.client.get("/api/working-shifts/"),
            self.client.get("/api/availability-exceptions/"),
            self.client.get("/api/appointments/"),
        )
        arrive_response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version},
            format="json",
        )
        appointment.refresh_from_db()
        check_in_response = self.client.post(
            f"/api/appointments/{appointment.id}/check-in/",
            {"version": appointment.version},
            format="json",
        )

        self.assertEqual(responses[0].status_code, status.HTTP_200_OK)
        for response in responses[1:]:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(arrive_response.status_code, status.HTTP_200_OK)
        self.assertEqual(check_in_response.status_code, status.HTTP_200_OK)

    def test_postponed_remains_non_blocking_with_visits_app_installed(self):
        self.set_clinic(capacity=1)
        postponed = self.make_visit_appointment(
            "postponed-nonblocking",
            status_value=Appointment.Status.POSTPONED,
        )
        new_appointment = self.make_visit_appointment(
            "after-postponed",
            status_value=Appointment.Status.SCHEDULED,
            start_at=BASE_AT + timedelta(minutes=30),
        )

        self.assertEqual(postponed.status, Appointment.Status.POSTPONED)
        self.assertEqual(new_appointment.status, Appointment.Status.SCHEDULED)
