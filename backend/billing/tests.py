from decimal import Decimal
from datetime import timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from employees.models import EmployeeProfile
from scheduling.models import Appointment
from scheduling.test_appointments import AppointmentTestHelpers, BASE_AT
from visits.models import Visit

from .models import Invoice, InvoiceAuditLog, Payment


class InvoiceTestHelpers(AppointmentTestHelpers):
    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def iso(self, value):
        return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")

    def make_visit_for_invoice(
        self,
        suffix,
        *,
        doctor_profile=None,
        patient=None,
        status_value=Visit.Status.COMPLETED,
        start_at=BASE_AT,
    ):
        appointment_status = (
            Appointment.Status.IN_VISIT
            if status_value == Visit.Status.ACTIVE
            else Appointment.Status.COMPLETED
        )
        appointment = self.make_appointment(
            patient or self.make_patient(suffix),
            doctor_profile or self.doctor_profile,
            status_value=appointment_status,
            start_at=start_at,
        )
        values = {
            "appointment": appointment,
            "patient": appointment.patient,
            "doctor_profile": appointment.doctor_profile,
            "status": status_value,
            "started_at": timezone.now(),
        }
        if status_value == Visit.Status.COMPLETED:
            values["completed_at"] = timezone.now()
        return Visit.objects.create(**values)

    def make_invoice(self, visit, *, amount="125.00", created_by=None, **overrides):
        values = {
            "visit": visit,
            "patient": visit.patient,
            "doctor_profile": visit.doctor_profile,
            "created_by": created_by,
            "total_amount": Decimal(amount),
            "note": "Invoice handoff",
        }
        values.update(overrides)
        return Invoice.objects.create(**values)

    def make_payment(self, invoice, *, amount="25.00", received_by=None, **overrides):
        values = {
            "invoice": invoice,
            "amount": Decimal(amount),
            "method": Payment.Method.CASH,
            "received_by": received_by,
            "note": "Cash payment",
        }
        values.update(overrides)
        return Payment.objects.create(**values)


class InvoiceModelTests(InvoiceTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=2)
        User = get_user_model()
        self.User = User
        self.doctor = self.make_user(User.Role.DOCTOR, "invoice-model-doctor@example.com")
        self.staff = self.make_user(User.Role.STAFF, "invoice-model-staff@example.com")
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-6100",
        )
        self.staff_profile = EmployeeProfile.objects.create(
            user=self.staff,
            specialty="",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-6101",
        )
        self.make_shift(self.doctor_profile)

    def test_invoice_can_be_created_for_visit_patient_and_doctor(self):
        visit = self.make_visit_for_invoice("model-create")

        invoice = self.make_invoice(visit, created_by=self.doctor)

        self.assertEqual(invoice.visit, visit)
        self.assertEqual(invoice.patient, visit.patient)
        self.assertEqual(invoice.doctor_profile, visit.doctor_profile)
        self.assertEqual(invoice.created_by, self.doctor)
        self.assertEqual(invoice.status, Invoice.Status.PENDING)
        self.assertEqual(invoice.version, 1)

    def test_invoice_patient_and_doctor_must_match_visit(self):
        visit = self.make_visit_for_invoice("model-match")
        other_patient = self.make_patient("invoice-other-patient")

        with self.assertRaises(ValidationError):
            self.make_invoice(visit, patient=other_patient)
        with self.assertRaises(ValidationError):
            self.make_invoice(visit, doctor_profile=self.staff_profile)

    def test_one_visit_cannot_have_duplicate_invoices(self):
        visit = self.make_visit_for_invoice("model-duplicate")
        self.make_invoice(visit)

        with self.assertRaises(ValidationError):
            self.make_invoice(visit)

    def test_total_amount_must_be_positive(self):
        visit = self.make_visit_for_invoice("model-positive")

        for amount in ("0.00", "-1.00"):
            with self.assertRaises(ValidationError):
                self.make_invoice(visit, amount=amount)

    def test_payment_can_be_created_for_invoice(self):
        visit = self.make_visit_for_invoice("model-payment")
        invoice = self.make_invoice(visit)

        payment = self.make_payment(invoice, amount="45.00", received_by=self.staff)

        self.assertEqual(payment.invoice, invoice)
        self.assertEqual(payment.amount, Decimal("45.00"))
        self.assertEqual(payment.method, Payment.Method.CASH)
        self.assertEqual(payment.received_by, self.staff)
        self.assertEqual(invoice.paid_amount, Decimal("45.00"))
        self.assertEqual(invoice.balance, Decimal("80.00"))

    def test_payment_amount_must_be_positive_and_not_exceed_balance(self):
        visit = self.make_visit_for_invoice("model-payment-validation")
        invoice = self.make_invoice(visit, amount="50.00")

        for amount in ("0.00", "-1.00", "50.01"):
            with self.assertRaises(ValidationError):
                self.make_payment(invoice, amount=amount)

    def test_payment_method_must_be_cash(self):
        visit = self.make_visit_for_invoice("model-payment-method")
        invoice = self.make_invoice(visit)

        with self.assertRaises(ValidationError):
            self.make_payment(invoice, method="Card")

    def test_cancelled_invoice_rejects_payment(self):
        visit = self.make_visit_for_invoice("model-cancelled-payment")
        invoice = self.make_invoice(visit, status=Invoice.Status.CANCELLED)

        with self.assertRaises(ValidationError):
            self.make_payment(invoice)


class InvoiceAPITests(InvoiceTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=2)
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-invoices@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-invoices@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-invoices@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-invoices@example.com",
        )
        self.inactive = self.make_user(
            User.Role.DOCTOR,
            "inactive-invoices@example.com",
            user_status=User.Status.INACTIVE,
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-6200",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-6201",
        )
        self.inactive_doctor_profile = EmployeeProfile.objects.create(
            user=self.inactive,
            specialty="Periodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-6202",
        )
        self.make_shift(self.doctor_profile)
        self.make_shift(self.other_doctor_profile)

    def invoice_payload(self, visit, *, amount="175.50", note="Doctor handoff"):
        return {
            "visitId": visit.id,
            "totalAmount": amount,
            "note": note,
        }

    def payment_payload(self, invoice, *, amount="50.00", method=Payment.Method.CASH, note="Cash payment"):
        payload = {
            "invoiceId": invoice.id,
            "amount": amount,
            "note": note,
        }
        if method is not None:
            payload["method"] = method
        return payload

    def test_doctor_can_create_invoice_for_own_completed_visit(self):
        visit = self.make_visit_for_invoice("api-create-completed")
        appointment_status = visit.appointment.status
        visit_status = visit.status
        self.authenticate(self.doctor)

        response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["visitId"], visit.id)
        self.assertEqual(response.data["appointmentId"], visit.appointment_id)
        self.assertEqual(response.data["patientId"], visit.patient_id)
        self.assertEqual(response.data["doctorProfileId"], self.doctor_profile.id)
        self.assertEqual(response.data["createdById"], self.doctor.id)
        self.assertEqual(response.data["totalAmount"], "175.50")
        self.assertEqual(response.data["status"], Invoice.Status.PENDING)
        self.assertEqual(response.data["version"], 1)
        invoice = Invoice.objects.get(visit=visit)
        self.assertEqual(invoice.created_by, self.doctor)
        visit.refresh_from_db()
        visit.appointment.refresh_from_db()
        self.assertEqual(visit.status, visit_status)
        self.assertEqual(visit.appointment.status, appointment_status)

    def test_doctor_cannot_create_invoice_for_active_visit(self):
        visit = self.make_visit_for_invoice(
            "api-create-active",
            status_value=Visit.Status.ACTIVE,
        )
        self.authenticate(self.doctor)

        response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit, amount="200.00"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Invoice.objects.filter(visit=visit).exists())
        visit.refresh_from_db()
        visit.appointment.refresh_from_db()
        self.assertEqual(visit.status, Visit.Status.ACTIVE)
        self.assertEqual(visit.appointment.status, Appointment.Status.IN_VISIT)

    def test_visit_invoice_alias_creates_invoice_handoff(self):
        visit = self.make_visit_for_invoice("api-create-alias")
        self.authenticate(self.doctor)

        response = self.client.post(
            f"/api/visits/{visit.id}/invoice/",
            {"totalAmount": "99.00", "note": "Alias handoff"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["visitId"], visit.id)
        self.assertEqual(response.data["totalAmount"], "99.00")

    def test_invoice_response_uses_camel_case_and_omits_payment_fields(self):
        visit = self.make_visit_for_invoice("api-shape")
        self.authenticate(self.doctor)

        response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for field in (
            "visitId",
            "appointmentId",
            "patientId",
            "patientName",
            "doctorProfileId",
            "doctorName",
            "createdById",
            "totalAmount",
            "paidAmount",
            "balance",
            "createdAt",
            "updatedAt",
        ):
            self.assertIn(field, response.data)
        self.assertEqual(response.data["paidAmount"], "0.00")
        self.assertEqual(response.data["balance"], "175.50")
        for forbidden in (
            "due",
            "dueAmount",
            "remainingBalance",
            "payments",
            "payment",
            "paymentMethod",
            "paymentStatus",
        ):
            self.assertNotIn(forbidden, response.data)

    def test_doctor_cannot_create_invoice_for_another_doctors_visit(self):
        visit = self.make_visit_for_invoice(
            "api-other-doctor",
            doctor_profile=self.other_doctor_profile,
        )
        self.authenticate(self.doctor)

        response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invoice_requires_existing_visit_and_rejects_duplicate_or_non_positive_amount(self):
        visit = self.make_visit_for_invoice("api-validation")
        scheduled_appointment = self.make_appointment(
            self.make_patient("no-visit"),
            self.doctor_profile,
            status_value=Appointment.Status.SCHEDULED,
            start_at=BASE_AT + timedelta(hours=1),
        )
        self.authenticate(self.doctor)

        invalid_visit_response = self.client.post(
            "/api/invoices/",
            {
                "visitId": scheduled_appointment.id,
                "totalAmount": "50.00",
            },
            format="json",
        )
        first_response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )
        duplicate_response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )
        zero_response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(
                self.make_visit_for_invoice("api-zero", start_at=BASE_AT + timedelta(hours=2)),
                amount="0.00",
            ),
            format="json",
        )
        negative_response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(
                self.make_visit_for_invoice("api-negative", start_at=BASE_AT + timedelta(hours=3)),
                amount="-1.00",
            ),
            format="json",
        )

        self.assertEqual(invalid_visit_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(zero_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(negative_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_staff_cannot_create_invoice_in_phase_10(self):
        visit = self.make_visit_for_invoice("api-staff-create")
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit, amount="80.00"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Invoice.objects.filter(visit=visit).exists())

    def test_admin_anonymous_and_inactive_users_cannot_create_invoice(self):
        visit = self.make_visit_for_invoice("api-create-permissions")

        anonymous_response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )
        self.authenticate(self.admin)
        admin_response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )
        self.authenticate(self.inactive)
        inactive_response = self.client.post(
            "/api/invoices/",
            self.invoice_payload(visit),
            format="json",
        )

        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            inactive_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_list_retrieve_and_filters_follow_role_scope(self):
        own_visit = self.make_visit_for_invoice("api-list-own")
        own_invoice = self.make_invoice(own_visit, created_by=self.doctor)
        other_visit = self.make_visit_for_invoice(
            "api-list-other",
            doctor_profile=self.other_doctor_profile,
            start_at=BASE_AT + timedelta(hours=1),
        )
        other_invoice = self.make_invoice(
            other_visit,
            created_by=self.other_doctor,
            amount="220.00",
        )
        date_from = timezone.now() - timedelta(minutes=10)
        date_to = timezone.now() + timedelta(minutes=10)

        self.authenticate(self.doctor)
        doctor_list = self.client.get("/api/invoices/")
        doctor_other_filter = self.client.get(
            "/api/invoices/",
            {"doctorProfileId": self.other_doctor_profile.id},
        )
        doctor_own_retrieve = self.client.get(f"/api/invoices/{own_invoice.id}/")
        doctor_other_retrieve = self.client.get(f"/api/invoices/{other_invoice.id}/")

        self.authenticate(self.staff)
        staff_list = self.client.get("/api/invoices/")
        staff_patient = self.client.get("/api/invoices/", {"patientId": own_visit.patient_id})
        staff_doctor = self.client.get(
            "/api/invoices/",
            {"doctorProfileId": self.other_doctor_profile.id},
        )
        staff_visit = self.client.get("/api/invoices/", {"visitId": own_visit.id})
        staff_status = self.client.get("/api/invoices/", {"status": Invoice.Status.PENDING})
        staff_range = self.client.get(
            "/api/invoices/",
            {
                "from": self.iso(date_from),
                "to": self.iso(date_to),
            },
        )
        staff_retrieve = self.client.get(f"/api/invoices/{other_invoice.id}/")

        self.authenticate(self.admin)
        admin_list = self.client.get("/api/invoices/")
        admin_own_retrieve = self.client.get(f"/api/invoices/{own_invoice.id}/")
        admin_retrieve = self.client.get(f"/api/invoices/{other_invoice.id}/")

        self.assertEqual(doctor_list.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in doctor_list.data["results"]}, {own_invoice.id})
        self.assertEqual(doctor_other_filter.data["results"], [])
        self.assertEqual(doctor_own_retrieve.status_code, status.HTTP_200_OK)
        self.assertEqual(doctor_other_retrieve.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_list.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in staff_list.data["results"]}, {own_invoice.id, other_invoice.id})
        self.assertEqual([item["id"] for item in staff_patient.data["results"]], [own_invoice.id])
        self.assertEqual([item["id"] for item in staff_doctor.data["results"]], [other_invoice.id])
        self.assertEqual([item["id"] for item in staff_visit.data["results"]], [own_invoice.id])
        self.assertEqual({item["id"] for item in staff_status.data["results"]}, {own_invoice.id, other_invoice.id})
        self.assertEqual({item["id"] for item in staff_range.data["results"]}, {own_invoice.id, other_invoice.id})
        self.assertEqual(staff_retrieve.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_list.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in admin_list.data["results"]}, {own_invoice.id, other_invoice.id})
        self.assertEqual(admin_own_retrieve.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_retrieve.status_code, status.HTTP_200_OK)

    def test_staff_can_edit_invoice_total_before_payment_with_reason_and_version(self):
        visit = self.make_visit_for_invoice("api-edit-total")
        invoice = self.make_invoice(visit, created_by=self.doctor)
        self.authenticate(self.staff)

        response = self.client.patch(
            f"/api/invoices/{invoice.id}/",
            {
                "totalAmount": "150.00",
                "version": invoice.version,
                "reason": "Corrected treatment charge",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totalAmount"], "150.00")
        self.assertEqual(response.data["paidAmount"], "0.00")
        self.assertEqual(response.data["balance"], "150.00")
        self.assertEqual(response.data["status"], Invoice.Status.PENDING)
        self.assertEqual(response.data["version"], 2)
        invoice.refresh_from_db()
        self.assertEqual(invoice.total_amount, Decimal("150.00"))
        self.assertEqual(invoice.version, 2)
        audit_log = InvoiceAuditLog.objects.get(invoice=invoice)
        self.assertEqual(audit_log.action, InvoiceAuditLog.Action.TOTAL_EDIT)
        self.assertEqual(audit_log.changed_by, self.staff)
        self.assertEqual(audit_log.reason, "Corrected treatment charge")

    def test_invoice_total_edit_requires_reason_version_and_current_version(self):
        missing_reason_invoice = self.make_invoice(
            self.make_visit_for_invoice("api-edit-missing-reason"),
        )
        missing_version_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-edit-missing-version",
                start_at=BASE_AT + timedelta(hours=1),
            ),
        )
        stale_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-edit-stale",
                start_at=BASE_AT + timedelta(hours=2),
            ),
        )
        self.authenticate(self.staff)

        missing_reason = self.client.patch(
            f"/api/invoices/{missing_reason_invoice.id}/",
            {
                "totalAmount": "140.00",
                "version": missing_reason_invoice.version,
            },
            format="json",
        )
        missing_version = self.client.patch(
            f"/api/invoices/{missing_version_invoice.id}/",
            {
                "totalAmount": "140.00",
                "reason": "Corrected treatment charge",
            },
            format="json",
        )
        stale = self.client.patch(
            f"/api/invoices/{stale_invoice.id}/",
            {
                "totalAmount": "140.00",
                "version": stale_invoice.version + 1,
                "reason": "Corrected treatment charge",
            },
            format="json",
        )

        self.assertEqual(missing_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_version.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)

    def test_invoice_total_edit_rejects_after_payment_paid_cancelled_and_wrong_roles(self):
        paid_visit = self.make_visit_for_invoice("api-edit-after-payment")
        paid_invoice = self.make_invoice(paid_visit, created_by=self.doctor)
        self.make_payment(paid_invoice, amount="25.00", received_by=self.staff)
        paid_status_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-edit-paid-status",
                start_at=BASE_AT + timedelta(hours=1),
            ),
            status=Invoice.Status.PAID,
        )
        cancelled_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-edit-cancelled",
                start_at=BASE_AT + timedelta(hours=2),
            ),
            status=Invoice.Status.CANCELLED,
        )
        role_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-edit-role",
                start_at=BASE_AT + timedelta(hours=3),
            ),
        )

        self.authenticate(self.staff)
        after_payment = self.client.patch(
            f"/api/invoices/{paid_invoice.id}/",
            {
                "totalAmount": "150.00",
                "version": paid_invoice.version,
                "reason": "Corrected treatment charge",
            },
            format="json",
        )
        paid_status = self.client.patch(
            f"/api/invoices/{paid_status_invoice.id}/",
            {
                "totalAmount": "150.00",
                "version": paid_status_invoice.version,
                "reason": "Corrected treatment charge",
            },
            format="json",
        )
        cancelled = self.client.patch(
            f"/api/invoices/{cancelled_invoice.id}/",
            {
                "totalAmount": "150.00",
                "version": cancelled_invoice.version,
                "reason": "Corrected treatment charge",
            },
            format="json",
        )

        self.authenticate(self.doctor)
        doctor_response = self.client.patch(
            f"/api/invoices/{role_invoice.id}/",
            {
                "totalAmount": "150.00",
                "version": role_invoice.version,
                "reason": "Corrected treatment charge",
            },
            format="json",
        )
        self.authenticate(self.admin)
        admin_response = self.client.patch(
            f"/api/invoices/{role_invoice.id}/",
            {
                "totalAmount": "150.00",
                "version": role_invoice.version,
                "reason": "Corrected treatment charge",
            },
            format="json",
        )

        self.assertEqual(after_payment.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(paid_status.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cancelled.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(doctor_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_cancel_pending_invoice_without_payments(self):
        visit = self.make_visit_for_invoice("api-cancel")
        invoice = self.make_invoice(visit, created_by=self.doctor)
        self.authenticate(self.staff)

        response = self.client.post(
            f"/api/invoices/{invoice.id}/cancel/",
            {"version": invoice.version, "reason": "Patient declined payment"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Invoice.Status.CANCELLED)
        self.assertEqual(response.data["version"], 2)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.CANCELLED)
        self.assertEqual(invoice.version, 2)
        audit_log = InvoiceAuditLog.objects.get(invoice=invoice)
        self.assertEqual(audit_log.action, InvoiceAuditLog.Action.CANCEL)
        self.assertEqual(audit_log.reason, "Patient declined payment")

    def test_invoice_cancel_requires_reason_version_and_current_version(self):
        missing_reason_invoice = self.make_invoice(
            self.make_visit_for_invoice("api-cancel-missing-reason"),
        )
        missing_version_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-cancel-missing-version",
                start_at=BASE_AT + timedelta(hours=1),
            ),
        )
        stale_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-cancel-stale",
                start_at=BASE_AT + timedelta(hours=2),
            ),
        )
        self.authenticate(self.staff)

        missing_reason = self.client.post(
            f"/api/invoices/{missing_reason_invoice.id}/cancel/",
            {"version": missing_reason_invoice.version},
            format="json",
        )
        missing_version = self.client.post(
            f"/api/invoices/{missing_version_invoice.id}/cancel/",
            {"reason": "Patient declined payment"},
            format="json",
        )
        stale = self.client.post(
            f"/api/invoices/{stale_invoice.id}/cancel/",
            {
                "version": stale_invoice.version + 1,
                "reason": "Patient declined payment",
            },
            format="json",
        )

        self.assertEqual(missing_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_version.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)

    def test_invoice_cancel_rejects_paid_partial_and_wrong_roles(self):
        partial_invoice = self.make_invoice(
            self.make_visit_for_invoice("api-cancel-partial"),
        )
        self.make_payment(partial_invoice, amount="25.00", received_by=self.staff)
        paid_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-cancel-paid",
                start_at=BASE_AT + timedelta(hours=1),
            ),
            status=Invoice.Status.PAID,
        )
        role_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-cancel-role",
                start_at=BASE_AT + timedelta(hours=2),
            ),
        )

        self.authenticate(self.staff)
        partial_response = self.client.post(
            f"/api/invoices/{partial_invoice.id}/cancel/",
            {"version": partial_invoice.version, "reason": "Patient declined payment"},
            format="json",
        )
        paid_response = self.client.post(
            f"/api/invoices/{paid_invoice.id}/cancel/",
            {"version": paid_invoice.version, "reason": "Patient declined payment"},
            format="json",
        )

        self.authenticate(self.doctor)
        doctor_response = self.client.post(
            f"/api/invoices/{role_invoice.id}/cancel/",
            {"version": role_invoice.version, "reason": "Patient declined payment"},
            format="json",
        )
        self.authenticate(self.admin)
        admin_response = self.client.post(
            f"/api/invoices/{role_invoice.id}/cancel/",
            {"version": role_invoice.version, "reason": "Patient declined payment"},
            format="json",
        )

        self.assertEqual(partial_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(paid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(doctor_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create_partial_and_full_cash_payments(self):
        visit = self.make_visit_for_invoice("api-payment")
        appointment_status = visit.appointment.status
        visit_status = visit.status
        invoice = self.make_invoice(visit, amount="100.00", created_by=self.doctor)
        self.authenticate(self.staff)

        partial_response = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="40.00"),
            format="json",
        )
        invoice.refresh_from_db()
        partial_invoice_response = self.client.get(f"/api/invoices/{invoice.id}/")
        full_response = self.client.post(
            f"/api/invoices/{invoice.id}/payments/",
            {"amount": "60.00", "method": Payment.Method.CASH, "note": "Final cash"},
            format="json",
        )
        invoice.refresh_from_db()
        full_invoice_response = self.client.get(f"/api/invoices/{invoice.id}/")
        visit.refresh_from_db()
        visit.appointment.refresh_from_db()

        self.assertEqual(partial_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(partial_response.data["invoiceId"], invoice.id)
        self.assertEqual(partial_response.data["amount"], "40.00")
        self.assertEqual(partial_response.data["method"], Payment.Method.CASH)
        self.assertEqual(partial_response.data["receivedById"], self.staff.id)
        self.assertIn("receivedByName", partial_response.data)
        self.assertIn("createdAt", partial_response.data)
        for forbidden in ("gateway", "card", "invoiceItems", "services", "serviceCatalog"):
            self.assertNotIn(forbidden, partial_response.data)
        self.assertEqual(partial_invoice_response.data["paidAmount"], "40.00")
        self.assertEqual(partial_invoice_response.data["balance"], "60.00")
        self.assertEqual(partial_invoice_response.data["status"], Invoice.Status.PARTIALLY_PAID)
        self.assertEqual(partial_invoice_response.data["version"], 2)
        self.assertEqual(full_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(full_invoice_response.data["paidAmount"], "100.00")
        self.assertEqual(full_invoice_response.data["balance"], "0.00")
        self.assertEqual(full_invoice_response.data["status"], Invoice.Status.PAID)
        self.assertEqual(full_invoice_response.data["version"], 3)
        self.assertEqual(visit.status, visit_status)
        self.assertEqual(visit.appointment.status, appointment_status)

    def test_payment_validation_rejects_overpayment_zero_negative_and_non_cash(self):
        invoice = self.make_invoice(
            self.make_visit_for_invoice("api-payment-validation"),
            amount="100.00",
        )
        self.authenticate(self.staff)

        overpayment = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="100.01"),
            format="json",
        )
        zero = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="0.00"),
            format="json",
        )
        negative = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="-1.00"),
            format="json",
        )
        non_cash = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="10.00", method="Card"),
            format="json",
        )

        self.assertEqual(overpayment.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(zero.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(negative.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(non_cash.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payment_on_cancelled_or_paid_invoice_is_rejected(self):
        cancelled_invoice = self.make_invoice(
            self.make_visit_for_invoice("api-payment-cancelled"),
        )
        paid_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-payment-paid",
                start_at=BASE_AT + timedelta(hours=1),
            ),
            amount="75.00",
        )
        self.authenticate(self.staff)
        cancel_response = self.client.post(
            f"/api/invoices/{cancelled_invoice.id}/cancel/",
            {"version": cancelled_invoice.version, "reason": "Patient declined payment"},
            format="json",
        )
        pay_full = self.client.post(
            "/api/payments/",
            self.payment_payload(paid_invoice, amount="75.00"),
            format="json",
        )
        cancelled_payment = self.client.post(
            "/api/payments/",
            self.payment_payload(cancelled_invoice, amount="10.00"),
            format="json",
        )
        paid_payment = self.client.post(
            "/api/payments/",
            self.payment_payload(paid_invoice, amount="1.00"),
            format="json",
        )

        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pay_full.status_code, status.HTTP_201_CREATED)
        self.assertEqual(cancelled_payment.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(paid_payment.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payment_permissions(self):
        invoice = self.make_invoice(
            self.make_visit_for_invoice("api-payment-permissions"),
        )

        anonymous_response = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="10.00"),
            format="json",
        )
        self.authenticate(self.doctor)
        doctor_response = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="10.00"),
            format="json",
        )
        self.authenticate(self.admin)
        admin_response = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="10.00"),
            format="json",
        )
        self.authenticate(self.inactive)
        inactive_response = self.client.post(
            "/api/payments/",
            self.payment_payload(invoice, amount="10.00"),
            format="json",
        )

        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(doctor_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            inactive_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_payment_list_retrieve_filters_and_role_scope(self):
        own_invoice = self.make_invoice(
            self.make_visit_for_invoice("api-payment-list-own"),
            amount="100.00",
            created_by=self.doctor,
        )
        own_payment = self.make_payment(own_invoice, amount="30.00", received_by=self.staff)
        other_invoice = self.make_invoice(
            self.make_visit_for_invoice(
                "api-payment-list-other",
                doctor_profile=self.other_doctor_profile,
                start_at=BASE_AT + timedelta(hours=1),
            ),
            amount="100.00",
            created_by=self.other_doctor,
        )
        other_payment = self.make_payment(other_invoice, amount="40.00", received_by=self.staff)
        date_from = timezone.now() - timedelta(minutes=10)
        date_to = timezone.now() + timedelta(minutes=10)

        self.authenticate(self.doctor)
        doctor_list = self.client.get("/api/payments/")
        doctor_invoice_payments = self.client.get(f"/api/invoices/{own_invoice.id}/payments/")
        doctor_other_retrieve = self.client.get(f"/api/payments/{other_payment.id}/")

        self.authenticate(self.staff)
        staff_list = self.client.get("/api/payments/")
        staff_invoice = self.client.get("/api/payments/", {"invoiceId": own_invoice.id})
        staff_patient = self.client.get("/api/payments/", {"patientId": own_invoice.patient_id})
        staff_doctor = self.client.get(
            "/api/payments/",
            {"doctorProfileId": self.other_doctor_profile.id},
        )
        staff_range = self.client.get(
            "/api/payments/",
            {"from": self.iso(date_from), "to": self.iso(date_to)},
        )
        staff_retrieve = self.client.get(f"/api/payments/{own_payment.id}/")

        self.authenticate(self.admin)
        admin_list = self.client.get("/api/payments/")
        admin_retrieve = self.client.get(f"/api/payments/{other_payment.id}/")

        self.assertEqual(doctor_list.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in doctor_list.data["results"]}, {own_payment.id})
        self.assertEqual(doctor_invoice_payments.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["id"] for item in doctor_invoice_payments.data["results"]},
            {own_payment.id},
        )
        self.assertEqual(doctor_other_retrieve.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_list.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in staff_list.data["results"]}, {own_payment.id, other_payment.id})
        self.assertEqual([item["id"] for item in staff_invoice.data["results"]], [own_payment.id])
        self.assertEqual([item["id"] for item in staff_patient.data["results"]], [own_payment.id])
        self.assertEqual([item["id"] for item in staff_doctor.data["results"]], [other_payment.id])
        self.assertEqual({item["id"] for item in staff_range.data["results"]}, {own_payment.id, other_payment.id})
        self.assertEqual(staff_retrieve.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_list.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in admin_list.data["results"]}, {own_payment.id, other_payment.id})
        self.assertEqual(admin_retrieve.status_code, status.HTTP_200_OK)

    def test_invoice_endpoints_reject_anonymous_and_inactive_list(self):
        anonymous_response = self.client.get("/api/invoices/")
        anonymous_payments = self.client.get("/api/payments/")
        self.authenticate(self.inactive)
        inactive_response = self.client.get("/api/invoices/")
        inactive_payments = self.client.get("/api/payments/")

        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(anonymous_payments.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(
            inactive_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            inactive_payments.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_regression_core_appointment_and_visit_endpoints_still_work(self):
        visit = self.make_visit_for_invoice(
            "api-regression-visit",
            status_value=Visit.Status.ACTIVE,
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
            self.client.get("/api/visits/"),
        )
        appointment_response = self.client.get(f"/api/appointments/{visit.appointment_id}/")
        visit_response = self.client.get(f"/api/visits/{visit.id}/")
        self.authenticate(self.doctor)
        active_visit_response = self.client.get("/api/visits/active/")
        complete_response = self.client.post(
            f"/api/visits/{visit.id}/complete/",
            {"version": visit.version},
            format="json",
        )

        self.assertEqual(responses[0].status_code, status.HTTP_200_OK)
        for response in responses[1:]:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(appointment_response.status_code, status.HTTP_200_OK)
        self.assertEqual(visit_response.status_code, status.HTTP_200_OK)
        for forbidden in (
            "due",
            "dueAmount",
            "balance",
            "payment",
            "paidAmount",
            "remainingBalance",
        ):
            self.assertNotIn(forbidden, appointment_response.data)
            self.assertNotIn(forbidden, visit_response.data)
        self.assertEqual(active_visit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)

    def test_postponed_remains_non_blocking_with_billing_app_installed(self):
        self.set_clinic(capacity=1)
        postponed = self.make_appointment(
            self.make_patient("invoice-postponed"),
            self.doctor_profile,
            status_value=Appointment.Status.POSTPONED,
        )
        new_appointment = self.make_appointment(
            self.make_patient("invoice-after-postponed"),
            self.doctor_profile,
            status_value=Appointment.Status.SCHEDULED,
            start_at=BASE_AT + timedelta(minutes=30),
        )

        self.assertEqual(postponed.status, Appointment.Status.POSTPONED)
        self.assertEqual(new_appointment.status, Appointment.Status.SCHEDULED)
