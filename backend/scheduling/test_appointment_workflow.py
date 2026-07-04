from datetime import timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from employees.models import EmployeeProfile

from .models import Appointment, AppointmentChangeLog, AvailabilityException, WorkingShift
from .test_appointments import AppointmentTestHelpers, BASE_AT


class AppointmentWorkflowTests(AppointmentTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=2)
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-workflow@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-workflow@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-workflow@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-workflow@example.com",
        )
        self.inactive = self.make_user(
            User.Role.STAFF,
            "inactive-workflow@example.com",
            user_status=User.Status.INACTIVE,
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-4100",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-4101",
        )
        self.make_shift(self.doctor_profile)
        self.make_shift(self.other_doctor_profile)

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def iso(self, value):
        return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")

    def make_workflow_appointment(
        self,
        suffix,
        *,
        status_value=None,
        start_at=BASE_AT,
        doctor_profile=None,
    ):
        return self.make_appointment(
            self.make_patient(suffix),
            doctor_profile or self.doctor_profile,
            status_value=status_value,
            start_at=start_at,
        )

    def reschedule_payload(self, start_at, *, doctor_profile=None, version=1, **overrides):
        payload = {
            "doctorProfileId": (doctor_profile or self.doctor_profile).id,
            "startAt": self.iso(start_at),
            "endAt": self.iso(start_at + timedelta(hours=1)),
            "durationMinutes": 60,
            "version": version,
            "reason": "Patient requested reschedule",
        }
        payload.update(overrides)
        return payload

    def leave_payload(self, start_at, end_at, *, status_value=None):
        payload = {
            "employeeProfileId": self.doctor_profile.id,
            "startAt": self.iso(start_at),
            "endAt": self.iso(end_at),
            "reason": "Leave",
        }
        if status_value:
            payload["status"] = status_value
        return payload

    def test_staff_workflow_actions_create_change_logs(self):
        self.authenticate(self.staff)
        cases = (
            (
                "arrive",
                Appointment.Status.SCHEDULED,
                Appointment.Status.ARRIVED,
                AppointmentChangeLog.Action.ARRIVE,
            ),
            (
                "check-in",
                Appointment.Status.ARRIVED,
                Appointment.Status.CHECKED_IN,
                AppointmentChangeLog.Action.CHECK_IN,
            ),
            (
                "cancel",
                Appointment.Status.CHECKED_IN,
                Appointment.Status.CANCELLED,
                AppointmentChangeLog.Action.CANCEL,
            ),
            (
                "no-show",
                Appointment.Status.ARRIVED,
                Appointment.Status.NO_SHOW,
                AppointmentChangeLog.Action.MARK_NO_SHOW,
            ),
            (
                "postpone",
                Appointment.Status.SCHEDULED,
                Appointment.Status.POSTPONED,
                AppointmentChangeLog.Action.POSTPONE,
            ),
            (
                "mark-needs-reschedule",
                Appointment.Status.CHECKED_IN,
                Appointment.Status.NEEDS_RESCHEDULE,
                AppointmentChangeLog.Action.MARK_NEEDS_RESCHEDULE,
            ),
        )

        for index, (action, old_status, new_status, log_action) in enumerate(cases):
            appointment = self.make_workflow_appointment(
                f"workflow-{action}",
                status_value=old_status,
                start_at=BASE_AT + timedelta(hours=index),
            )

            response = self.client.post(
                f"/api/appointments/{appointment.id}/{action}/",
                {"version": appointment.version, "reason": "Front desk update"},
                format="json",
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["status"], new_status)
            self.assertEqual(response.data["version"], 2)
            log = AppointmentChangeLog.objects.get(appointment=appointment)
            self.assertEqual(log.action, log_action)
            self.assertEqual(log.previous_status, old_status)
            self.assertEqual(log.new_status, new_status)
            self.assertEqual(log.changed_by, self.staff)
            self.assertEqual(log.reason, "Front desk update")

    def test_staff_cannot_check_in_directly_from_scheduled(self):
        appointment = self.make_workflow_appointment("direct-check-in")
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/check-in/",
            {"version": appointment.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)
        self.assertFalse(AppointmentChangeLog.objects.filter(appointment=appointment).exists())

    def test_terminal_statuses_cannot_be_changed_by_workflow(self):
        self.authenticate(self.staff)
        for index, terminal_status in enumerate(Appointment.TERMINAL_STATUSES):
            appointment = self.make_workflow_appointment(
                f"terminal-{terminal_status}",
                status_value=terminal_status,
                start_at=BASE_AT + timedelta(hours=index),
            )

            response = self.client.post(
                f"/api/appointments/{appointment.id}/arrive/",
                {"version": appointment.version},
                format="json",
            )

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            appointment.refresh_from_db()
            self.assertEqual(appointment.status, terminal_status)

    def test_workflow_permissions_keep_admin_and_doctor_read_only(self):
        appointment = self.make_workflow_appointment("permissions")

        anonymous_response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version},
            format="json",
        )
        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.authenticate(self.admin)
        admin_response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version},
            format="json",
        )
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.doctor)
        own_retrieve_response = self.client.get(f"/api/appointments/{appointment.id}/")
        doctor_response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version},
            format="json",
        )
        self.assertEqual(own_retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(doctor_response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.inactive)
        inactive_response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version},
            format="json",
        )
        self.assertIn(
            inactive_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        self.authenticate(self.staff)
        staff_response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version},
            format="json",
        )
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)

    def test_doctor_cannot_retrieve_other_doctor_appointment(self):
        appointment = self.make_workflow_appointment(
            "other-doctor-read",
            doctor_profile=self.other_doctor_profile,
        )
        self.authenticate(self.doctor)

        response = self.client.get(f"/api/appointments/{appointment.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stale_workflow_version_returns_409(self):
        appointment = self.make_workflow_appointment("stale-workflow")
        Appointment.objects.filter(pk=appointment.pk).update(version=3)
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Version conflict")
        self.assertEqual(response.data["currentVersion"], 3)

    def test_staff_still_cannot_use_start_visit_endpoint(self):
        appointment = self.make_workflow_appointment(
            "staff-start-visit",
            status_value=Appointment.Status.CHECKED_IN,
        )
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/start-visit/",
            {"version": appointment.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CHECKED_IN)

    def test_reschedule_queue_returns_needs_reschedule_for_admin_and_staff(self):
        queued = self.make_workflow_appointment(
            "queue-needs",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        self.make_workflow_appointment(
            "queue-scheduled",
            start_at=BASE_AT + timedelta(hours=1),
        )

        self.authenticate(self.admin)
        admin_response = self.client.get("/api/appointments/reschedule-queue/")
        self.authenticate(self.staff)
        staff_response = self.client.get("/api/appointments/reschedule-queue/")
        self.authenticate(self.doctor)
        doctor_response = self.client.get("/api/appointments/reschedule-queue/")

        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)
        self.assertEqual(doctor_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual([item["id"] for item in staff_response.data["results"]], [queued.id])

    def test_change_logs_are_readable_by_staff_admin_and_own_doctor(self):
        appointment = self.make_workflow_appointment("change-log-list")
        self.authenticate(self.staff)
        workflow_response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version, "reason": "Arrived at reception"},
            format="json",
        )
        staff_response = self.client.get(
            f"/api/appointments/{appointment.id}/change-logs/"
        )

        self.authenticate(self.admin)
        admin_response = self.client.get(
            f"/api/appointments/{appointment.id}/change-logs/"
        )
        self.authenticate(self.doctor)
        doctor_response = self.client.get(
            f"/api/appointments/{appointment.id}/change-logs/"
        )
        self.authenticate(self.other_doctor)
        other_doctor_response = self.client.get(
            f"/api/appointments/{appointment.id}/change-logs/"
        )

        self.assertEqual(workflow_response.status_code, status.HTTP_200_OK)
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(doctor_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_doctor_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(len(staff_response.data["results"]), 1)
        self.assertEqual(
            staff_response.data["results"][0]["action"],
            AppointmentChangeLog.Action.ARRIVE,
        )
        self.assertEqual(
            staff_response.data["results"][0]["reason"],
            "Arrived at reception",
        )

    def test_staff_can_reschedule_needs_reschedule_to_scheduled_with_change_log(self):
        appointment = self.make_workflow_appointment(
            "reschedule-needs",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        new_start = BASE_AT + timedelta(days=7, hours=1)
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(new_start, version=appointment.version),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["appointment"]["status"], Appointment.Status.SCHEDULED)
        self.assertEqual(response.data["appointment"]["version"], 2)
        self.assertIn("changeLog", response.data)
        log = AppointmentChangeLog.objects.get(appointment=appointment)
        self.assertEqual(log.action, AppointmentChangeLog.Action.RESCHEDULE)
        self.assertEqual(log.previous_status, Appointment.Status.NEEDS_RESCHEDULE)
        self.assertEqual(log.new_status, Appointment.Status.SCHEDULED)
        self.assertEqual(log.old_doctor_profile, self.doctor_profile)
        self.assertEqual(log.new_doctor_profile, self.doctor_profile)
        self.assertEqual(log.changed_by, self.staff)
        self.assertEqual(log.reason, "Patient requested reschedule")

    def test_staff_can_reschedule_postponed_to_scheduled(self):
        appointment = self.make_workflow_appointment(
            "reschedule-postponed",
            status_value=Appointment.Status.POSTPONED,
        )
        new_start = BASE_AT + timedelta(days=7, hours=2)
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(new_start, version=appointment.version),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["appointment"]["status"], Appointment.Status.SCHEDULED)
        self.assertEqual(AppointmentChangeLog.objects.get(appointment=appointment).new_status, Appointment.Status.SCHEDULED)

    def test_reschedule_rejects_non_queue_status(self):
        appointment = self.make_workflow_appointment("reschedule-scheduled")
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(BASE_AT + timedelta(days=7), version=appointment.version),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_reschedule_revalidates_working_shift(self):
        appointment = self.make_workflow_appointment(
            "reschedule-shift",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(
                BASE_AT + timedelta(days=7, hours=9),
                version=appointment.version,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_reschedule_rejects_active_leave_conflict(self):
        appointment = self.make_workflow_appointment(
            "reschedule-leave",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        new_start = BASE_AT + timedelta(days=7, hours=1)
        AvailabilityException.objects.create(
            employee_profile=self.doctor_profile,
            start_at=new_start,
            end_at=new_start + timedelta(hours=1),
            reason=AvailabilityException.Reason.LEAVE,
        )
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(new_start, version=appointment.version),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_reschedule_rejects_same_doctor_overlap(self):
        appointment = self.make_workflow_appointment(
            "reschedule-overlap",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        new_start = BASE_AT + timedelta(days=7, hours=1)
        self.make_workflow_appointment("existing-overlap", start_at=new_start)
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(new_start, version=appointment.version),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_reschedule_rejects_capacity_exceeded(self):
        self.set_clinic(capacity=1)
        appointment = self.make_workflow_appointment(
            "reschedule-capacity",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        new_start = BASE_AT + timedelta(days=7, hours=1)
        self.make_workflow_appointment(
            "capacity-existing",
            doctor_profile=self.other_doctor_profile,
            start_at=new_start,
        )
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(new_start, version=appointment.version),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.data)

    def test_reschedule_ignores_current_appointment_for_overlap_and_capacity(self):
        self.set_clinic(capacity=1)
        appointment = self.make_workflow_appointment(
            "reschedule-self",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/reschedule/",
            self.reschedule_payload(BASE_AT, version=appointment.version),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["appointment"]["status"], Appointment.Status.SCHEDULED)

    def test_reschedule_version_errors_are_reported(self):
        missing_version = self.make_workflow_appointment(
            "reschedule-missing-version",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
        )
        stale = self.make_workflow_appointment(
            "reschedule-stale-version",
            status_value=Appointment.Status.NEEDS_RESCHEDULE,
            start_at=BASE_AT + timedelta(hours=1),
        )
        Appointment.objects.filter(pk=stale.pk).update(version=4)
        self.authenticate(self.staff)

        missing_payload = self.reschedule_payload(
            BASE_AT + timedelta(days=7),
            version=missing_version.version,
        )
        missing_payload.pop("version")
        missing_response = self.client.post(
            f"/api/appointments/{missing_version.id}/reschedule/",
            missing_payload,
            format="json",
        )
        stale_response = self.client.post(
            f"/api/appointments/{stale.id}/reschedule/",
            self.reschedule_payload(
                BASE_AT + timedelta(days=7, hours=1),
                version=1,
            ),
            format="json",
        )

        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", missing_response.data)
        self.assertEqual(stale_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(stale_response.data["currentVersion"], 4)

    def test_postponed_remains_non_blocking_after_workflow_action(self):
        self.set_clinic(capacity=1)
        appointment = self.make_workflow_appointment("postponed-nonblocking")
        self.authenticate(self.staff)

        postpone_response = self.client.post(
            f"/api/appointments/{appointment.id}/postpone/",
            {"version": appointment.version},
            format="json",
        )
        create_response = self.client.post(
            "/api/appointments/",
            {
                "patientId": self.make_patient("after-postpone").id,
                "doctorProfileId": self.doctor_profile.id,
                "startAt": self.iso(BASE_AT + timedelta(minutes=30)),
                "endAt": self.iso(BASE_AT + timedelta(minutes=90)),
                "durationMinutes": 60,
                "visitType": "Routine Checkup",
            },
            format="json",
        )

        self.assertEqual(postpone_response.status_code, status.HTTP_200_OK)
        self.assertEqual(postpone_response.data["status"], Appointment.Status.POSTPONED)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

    def test_appointment_response_still_omits_billing_fields(self):
        appointment = self.make_workflow_appointment("no-billing")
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/appointments/{appointment.id}/arrive/",
            {"version": appointment.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in ("due", "dueAmount", "balance", "invoice", "payment"):
            self.assertNotIn(field, response.data)

    def test_active_leave_marks_affected_appointments_and_creates_logs(self):
        self.authenticate(self.admin)
        shift_snapshot = (
            WorkingShift.objects.get(employee_profile=self.doctor_profile).is_active,
            WorkingShift.objects.get(employee_profile=self.doctor_profile).version,
        )
        affected_statuses = (
            Appointment.Status.SCHEDULED,
            Appointment.Status.ARRIVED,
            Appointment.Status.CHECKED_IN,
            Appointment.Status.NEEDS_RESCHEDULE,
        )
        affected = [
            self.make_workflow_appointment(
                f"leave-affected-{index}",
                status_value=status_value,
                start_at=BASE_AT + timedelta(hours=index),
            )
            for index, status_value in enumerate(affected_statuses)
        ]
        skipped = [
            self.make_workflow_appointment(
                "leave-cancelled",
                status_value=Appointment.Status.CANCELLED,
                start_at=BASE_AT + timedelta(hours=4),
            ),
            self.make_workflow_appointment(
                "leave-no-show",
                status_value=Appointment.Status.NO_SHOW,
                start_at=BASE_AT + timedelta(hours=5),
            ),
            self.make_workflow_appointment(
                "leave-completed",
                status_value=Appointment.Status.COMPLETED,
                start_at=BASE_AT + timedelta(hours=6),
            ),
            self.make_workflow_appointment(
                "leave-postponed",
                status_value=Appointment.Status.POSTPONED,
                start_at=BASE_AT + timedelta(hours=7),
            ),
        ]

        response = self.client.post(
            "/api/availability-exceptions/",
            self.leave_payload(BASE_AT, BASE_AT + timedelta(hours=8)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for appointment in affected:
            appointment.refresh_from_db()
            self.assertEqual(appointment.status, Appointment.Status.NEEDS_RESCHEDULE)
            self.assertEqual(appointment.version, 2)
            self.assertEqual(
                AppointmentChangeLog.objects.get(appointment=appointment).new_status,
                Appointment.Status.NEEDS_RESCHEDULE,
            )
        for appointment in skipped:
            original_status = appointment.status
            appointment.refresh_from_db()
            self.assertEqual(appointment.status, original_status)
            self.assertEqual(appointment.version, 1)
        shift = WorkingShift.objects.get(employee_profile=self.doctor_profile)
        self.assertEqual((shift.is_active, shift.version), shift_snapshot)

    def test_cancelled_leave_does_not_mark_appointments(self):
        appointment = self.make_workflow_appointment("cancelled-leave-side-effect")
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/availability-exceptions/",
            self.leave_payload(
                BASE_AT,
                BASE_AT + timedelta(hours=1),
                status_value=AvailabilityException.Status.CANCELLED,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)
        self.assertFalse(AppointmentChangeLog.objects.filter(appointment=appointment).exists())

    def test_in_visit_overlap_rejects_active_leave(self):
        appointment = self.make_workflow_appointment(
            "in-visit-leave",
            status_value=Appointment.Status.IN_VISIT,
        )
        self.authenticate(self.admin)

        response = self.client.post(
            "/api/availability-exceptions/",
            self.leave_payload(BASE_AT, BASE_AT + timedelta(hours=1)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.IN_VISIT)

    def test_updating_active_leave_marks_affected_and_cancel_does_not_restore(self):
        appointment = self.make_workflow_appointment("leave-update-side-effect")
        exception = AvailabilityException.objects.create(
            employee_profile=self.doctor_profile,
            start_at=BASE_AT + timedelta(days=7),
            end_at=BASE_AT + timedelta(days=7, hours=1),
            reason=AvailabilityException.Reason.LEAVE,
        )
        self.authenticate(self.admin)

        update_response = self.client.patch(
            f"/api/availability-exceptions/{exception.id}/",
            {
                "startAt": self.iso(BASE_AT),
                "endAt": self.iso(BASE_AT + timedelta(hours=1)),
                "version": exception.version,
            },
            format="json",
        )
        cancel_response = self.client.patch(
            f"/api/availability-exceptions/{exception.id}/",
            {
                "status": AvailabilityException.Status.CANCELLED,
                "version": update_response.data["version"],
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.NEEDS_RESCHEDULE)
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.NEEDS_RESCHEDULE)

    def test_regression_endpoints_still_work_after_workflow_additions(self):
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

        self.assertEqual(responses[0].status_code, status.HTTP_200_OK)
        for response in responses[1:]:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
