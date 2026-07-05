from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from ai_results.models import AIResult
from ai_results.tests import AIResultTestHelpers
from attachments.tests import TempMediaMixin
from billing.models import Invoice, Payment
from employees.models import EmployeeProfile
from patients.models import Patient
from scheduling.models import Appointment
from scheduling.test_appointments import BASE_AT
from visits.models import Visit


class FrontendAPIAlignmentSmokeTests(TempMediaMixin, AIResultTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=4)
        User = get_user_model()
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-api-alignment@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-api-alignment@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-api-alignment@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-api-alignment@example.com",
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-9100",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-9101",
        )
        self.staff_profile = EmployeeProfile.objects.create(
            user=self.staff,
            specialty="",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-9102",
        )
        self.make_shift(self.doctor_profile)
        self.make_shift(self.other_doctor_profile)

    def test_auth_roles_and_settings_contract_uses_simple_camel_case_shapes(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {
                "username": self.staff.username,
                "password": "test-pass-123",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        for field in ("access", "refresh", "accessToken", "refreshToken", "user"):
            self.assertIn(field, login_response.data)
        self.assertEqual(login_response.data["access"], login_response.data["accessToken"])
        self.assertEqual(login_response.data["refresh"], login_response.data["refreshToken"])
        self.assertEqual(login_response.data["user"]["phone"], self.staff_profile.phone)
        self.assertIn("createdAt", login_response.data["user"])
        self.assertNotIn("rolePermissions", login_response.data)
        self.assertNotIn("permissions", login_response.data["user"])

        self.authenticate(self.staff)
        me_response = self.client.get("/api/auth/me/")
        roles_response = self.client.get("/api/auth/roles/")
        settings_response = self.client.get("/api/clinic/settings/")

        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["role"], "Staff")
        self.assertIn("mustChangePassword", me_response.data)
        self.assertEqual(roles_response.status_code, status.HTTP_200_OK)
        self.assertEqual(roles_response.data, {"roles": ["Admin", "Staff", "Doctor"]})
        self.assertEqual(settings_response.status_code, status.HTTP_200_OK)
        self.assertIn("clinicTimezone", settings_response.data)
        self.assertIn("maxSimultaneousAppointments", settings_response.data)
        self.assertNotIn("clinic_timezone", settings_response.data)

    def test_patient_shift_and_appointment_contracts_match_source_decisions(self):
        self.authenticate(self.staff)
        patient_response = self.client.post(
            "/api/patients/",
            {
                "firstName": "Maya",
                "lastName": "Rivera",
                "gender": Patient.Gender.FEMALE,
                "dateOfBirth": date(1990, 1, 1).isoformat(),
                "phoneNumber": "+1-555-9200",
                "email": "maya.rivera@example.com",
                "nationalIdOrPassport": "A-123-XYZ",
                "medicalConditionsHistory": "None",
                "bloodGroup": Patient.BloodGroup.O_POSITIVE,
                "insuranceInfo": "Plan A",
                "emergencyContact": "Leo Rivera",
                "address": "100 Market Street",
            },
            format="json",
        )
        self.assertEqual(patient_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(patient_response.data["patientId"], patient_response.data["id"])
        self.assertEqual(patient_response.data["gender"], "Female")
        self.assertEqual(patient_response.data["nationalIdOrPassport"], "A-123-XYZ")
        self.assertIsInstance(patient_response.data["age"], int)
        for forbidden in ("sex", "national_id_or_passport", "Patient_ID"):
            self.assertNotIn(forbidden, patient_response.data)

        update_response = self.client.patch(
            f"/api/patients/{patient_response.data['id']}/",
            {"phoneNumber": "+1-555-9201", "version": patient_response.data["version"]},
            format="json",
        )
        stale_response = self.client.patch(
            f"/api/patients/{patient_response.data['id']}/",
            {"phoneNumber": "+1-555-9202", "version": patient_response.data["version"]},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["version"], 2)
        self.assertEqual(stale_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(stale_response.data["currentVersion"], 2)

        self.authenticate(self.admin)
        shift_response = self.client.get("/api/working-shifts/")
        self.assertEqual(shift_response.status_code, status.HTTP_200_OK)
        self.assertIn("isActive", shift_response.data["results"][0])
        self.assertNotIn("isOnLeave", shift_response.data["results"][0])

        self.authenticate(self.staff)
        appointment_response = self.client.post(
            "/api/appointments/",
            {
                "patientId": patient_response.data["id"],
                "doctorProfileId": self.doctor_profile.id,
                "visitType": Appointment.VisitType.ROUTINE_CHECKUP,
                "startAt": self.iso(BASE_AT + timedelta(hours=1)),
                "endAt": self.iso(BASE_AT + timedelta(hours=2)),
                "durationMinutes": 60,
                "notes": "Alignment appointment",
            },
            format="json",
        )
        self.assertEqual(appointment_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(appointment_response.data["status"], Appointment.Status.SCHEDULED)
        self.assertIn("doctorProfileId", appointment_response.data)
        self.assertIn("startAt", appointment_response.data)
        self.assertIn("endAt", appointment_response.data)
        for forbidden in ("due", "dueAmount", "paidAmount", "balance", "payment"):
            self.assertNotIn(forbidden, appointment_response.data)

    def test_billing_attachment_and_ai_contracts_are_frontend_ready_without_side_effects(self):
        completed_visit = self.make_visit_for_attachment(
            "alignment-invoice",
            status_value=Visit.Status.COMPLETED,
            start_at=BASE_AT + timedelta(hours=1),
        )
        active_visit = self.make_visit_for_attachment(
            "alignment-ai",
            status_value=Visit.Status.ACTIVE,
            start_at=BASE_AT + timedelta(hours=2),
        )

        self.authenticate(self.doctor)
        invoice_response = self.client.post(
            "/api/invoices/",
            {
                "visitId": completed_visit.id,
                "totalAmount": "200.00",
                "note": "Doctor treatment handoff",
            },
            format="json",
        )
        self.assertEqual(invoice_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(invoice_response.data["doctorProfileId"], self.doctor_profile.id)
        self.assertEqual(invoice_response.data["paidAmount"], "0.00")
        self.assertEqual(invoice_response.data["balance"], "200.00")
        self.assertEqual(invoice_response.data["status"], Invoice.Status.PENDING)
        for forbidden in ("due", "dueAmount", "remainingBalance", "invoiceItems", "services"):
            self.assertNotIn(forbidden, invoice_response.data)

        self.authenticate(self.staff)
        payment_response = self.client.post(
            "/api/payments/",
            {
                "invoiceId": invoice_response.data["id"],
                "amount": "75.00",
                "method": Payment.Method.CASH,
                "note": "Cash received",
            },
            format="json",
        )
        refreshed_invoice_response = self.client.get(
            f"/api/invoices/{invoice_response.data['id']}/"
        )
        self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(payment_response.data["method"], Payment.Method.CASH)
        self.assertEqual(refreshed_invoice_response.data["paidAmount"], "75.00")
        self.assertEqual(refreshed_invoice_response.data["balance"], "125.00")
        self.assertEqual(
            refreshed_invoice_response.data["status"],
            Invoice.Status.PARTIALLY_PAID,
        )
        completed_visit.refresh_from_db()
        completed_visit.appointment.refresh_from_db()
        self.assertEqual(completed_visit.status, Visit.Status.COMPLETED)
        self.assertEqual(completed_visit.appointment.status, Appointment.Status.COMPLETED)

        attachment = self.make_attachment(
            active_visit.patient,
            visit=active_visit,
            uploaded_by=self.doctor,
        )
        attachment_response = self.client.get(f"/api/attachments/{attachment.id}/")
        self.assertEqual(attachment_response.status_code, status.HTTP_200_OK)
        for field in ("fileUrl", "originalFilename", "contentType", "uploadedById"):
            self.assertIn(field, attachment_response.data)
        self.assertNotIn("filePath", attachment_response.data)

        ai_response = self.client.post(
            "/api/ai-results/",
            self.ai_payload(
                attachment,
                findings=[
                    {
                        "toothFdi": "11",
                        "diseaseLabel": "Caries",
                        "confidence": 0.76,
                    }
                ],
            ),
            format="json",
        )
        missing_inference_response = self.client.post("/api/predict/", {}, format="json")
        self.assertEqual(ai_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ai_response.data["attachmentId"], attachment.id)
        self.assertEqual(ai_response.data["modelName"], "Storage metadata model")
        self.assertEqual(ai_response.data["modelVersion"], "v1.0.0")
        self.assertIn("overlayUrl", ai_response.data)
        self.assertEqual(ai_response.data["findings"][0]["toothFdi"], "11")
        for forbidden in (
            "clinicalDiagnosis",
            "finalDiagnosis",
            "diagnosis",
            "treatmentPlan",
            "due",
            "payment",
        ):
            self.assertNotIn(forbidden, ai_response.data)
        self.assertEqual(missing_inference_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(AIResult.objects.count(), 1)
