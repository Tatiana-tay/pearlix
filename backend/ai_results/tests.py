from datetime import timedelta, timezone as datetime_timezone

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from attachments.models import Attachment
from attachments.tests import AttachmentTestHelpers, TempMediaMixin
from billing.models import Invoice
from employees.models import EmployeeProfile
from scheduling.models import Appointment
from scheduling.test_appointments import BASE_AT
from visits.models import Visit

from .models import AIResult, AIResultFinding


class AIResultTestHelpers(AttachmentTestHelpers):
    def make_ai_result(
        self,
        attachment,
        *,
        created_by=None,
        status_value=AIResult.Status.COMPLETED,
        model_name="Storage metadata model",
        model_version="v1.0.0",
        overall_confidence=0.86,
        **overrides,
    ):
        values = {
            "attachment": attachment,
            "patient": attachment.patient,
            "visit": attachment.visit,
            "status": status_value,
            "result_summary": "Support finding metadata only",
            "model_name": model_name,
            "model_version": model_version,
            "overall_confidence": overall_confidence,
            "overlay_url": "/authorized/overlay/example.png",
            "error_message": "",
            "metadata": {"source": "test-import"},
            "created_by": created_by,
        }
        values.update(overrides)
        return AIResult.objects.create(**values)

    def make_finding(
        self,
        ai_result,
        *,
        tooth_fdi="11",
        disease_label="Caries",
        confidence=0.75,
        **overrides,
    ):
        values = {
            "ai_result": ai_result,
            "tooth_fdi": tooth_fdi,
            "disease_label": disease_label,
            "confidence": confidence,
            "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
            "mask": {"format": "polygon", "points": [[1, 2], [3, 4]]},
            "metadata": {"supportOnly": True},
        }
        values.update(overrides)
        return AIResultFinding.objects.create(**values)

    def ai_payload(
        self,
        attachment,
        *,
        status_value=AIResult.Status.COMPLETED,
        model_name="Storage metadata model",
        model_version="v1.0.0",
        overall_confidence=0.86,
        findings=None,
        **overrides,
    ):
        payload = {
            "attachmentId": attachment.id,
            "status": status_value,
            "resultSummary": "Support finding metadata only",
            "modelName": model_name,
            "modelVersion": model_version,
            "overallConfidence": overall_confidence,
            "overlayUrl": "/authorized/overlay/example.png",
            "errorMessage": "",
            "metadata": {"source": "api-import"},
        }
        if findings is not None:
            payload["findings"] = findings
        payload.update(overrides)
        return payload


class AIResultModelTests(TempMediaMixin, AIResultTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=3)
        User = get_user_model()
        self.doctor = self.make_user(User.Role.DOCTOR, "ai-model-doctor@example.com")
        self.staff = self.make_user(User.Role.STAFF, "ai-model-staff@example.com")
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-8100",
        )
        self.make_shift(self.doctor_profile)

    def test_ai_result_can_be_created_for_attachment_and_derives_context(self):
        visit = self.make_visit_for_attachment("model-create")
        attachment = self.make_attachment(visit.patient, visit=visit, uploaded_by=self.doctor)

        ai_result = AIResult.objects.create(
            attachment=attachment,
            status=AIResult.Status.COMPLETED,
            model_name="Plain metadata model",
            model_version="2026.07",
            overall_confidence=0.91,
            created_by=self.staff,
        )

        self.assertEqual(ai_result.attachment, attachment)
        self.assertEqual(ai_result.patient, attachment.patient)
        self.assertEqual(ai_result.visit, attachment.visit)
        self.assertEqual(ai_result.model_name, "Plain metadata model")
        self.assertEqual(ai_result.model_version, "2026.07")
        self.assertEqual(ai_result.overall_confidence, 0.91)
        self.assertEqual(ai_result.created_by, self.staff)

    def test_ai_result_rejects_patient_visit_status_and_confidence_mismatch(self):
        visit = self.make_visit_for_attachment("model-validation")
        attachment = self.make_attachment(visit.patient, visit=visit)
        other_patient = self.make_patient("ai-model-other-patient")
        other_visit = self.make_visit_for_attachment(
            "model-other-visit",
            patient=other_patient,
            status_value=Visit.Status.COMPLETED,
            start_at=BASE_AT + timedelta(hours=1),
        )

        for overrides in (
            {"patient": other_patient},
            {"visit": other_visit},
            {"status": "Diagnosed"},
            {"overall_confidence": 1.01},
            {"overall_confidence": -0.01},
        ):
            with self.assertRaises(ValidationError):
                self.make_ai_result(attachment, **overrides)

    def test_failed_result_can_store_error_and_multiple_results_per_attachment(self):
        visit = self.make_visit_for_attachment("model-multiple")
        attachment = self.make_attachment(visit.patient, visit=visit)

        failed = self.make_ai_result(
            attachment,
            status_value=AIResult.Status.FAILED,
            overall_confidence=None,
            error_message="Import failed before any model execution.",
        )
        second = self.make_ai_result(
            attachment,
            model_version="v2.0.0",
            overall_confidence=0.66,
        )

        self.assertEqual(failed.error_message, "Import failed before any model execution.")
        self.assertEqual(
            set(AIResult.objects.filter(attachment=attachment).values_list("id", flat=True)),
            {failed.id, second.id},
        )

    def test_finding_validation_and_optional_metadata_fields(self):
        visit = self.make_visit_for_attachment("model-finding")
        attachment = self.make_attachment(visit.patient, visit=visit)
        ai_result = self.make_ai_result(attachment)

        finding = self.make_finding(ai_result)

        self.assertEqual(finding.tooth_fdi, "11")
        self.assertEqual(finding.disease_label, "Caries")
        self.assertEqual(finding.confidence, 0.75)
        self.assertEqual(finding.bbox["width"], 3)
        self.assertEqual(finding.mask["format"], "polygon")

        for overrides in (
            {"tooth_fdi": "19"},
            {"tooth_fdi": "55"},
            {"disease_label": ""},
            {"confidence": 1.01},
            {"confidence": -0.01},
        ):
            with self.assertRaises(ValidationError):
                self.make_finding(ai_result, **overrides)


class AIResultAPITests(TempMediaMixin, AIResultTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=3)
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-ai-results@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-ai-results@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-ai-results@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-ai-results@example.com",
        )
        self.inactive = self.make_user(
            User.Role.DOCTOR,
            "inactive-ai-results@example.com",
            user_status=User.Status.INACTIVE,
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-8200",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-8201",
        )
        self.make_shift(self.doctor_profile)
        self.make_shift(self.other_doctor_profile)

    def test_staff_can_store_completed_ai_result_with_nested_findings(self):
        visit = self.make_visit_for_attachment("api-staff-create")
        attachment = self.make_attachment(visit.patient, visit=visit, uploaded_by=self.doctor)
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/ai-results/",
            self.ai_payload(
                attachment,
                findings=[
                    {
                        "toothFdi": "11",
                        "diseaseLabel": "Caries",
                        "confidence": 0.76,
                        "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
                        "mask": {"format": "polygon"},
                        "metadata": {"display": "support"},
                    }
                ],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["attachmentId"], attachment.id)
        self.assertEqual(response.data["patientId"], attachment.patient_id)
        self.assertEqual(response.data["patientName"], attachment.patient.full_name)
        self.assertEqual(response.data["visitId"], visit.id)
        self.assertEqual(response.data["status"], AIResult.Status.COMPLETED)
        self.assertEqual(response.data["modelName"], "Storage metadata model")
        self.assertEqual(response.data["modelVersion"], "v1.0.0")
        self.assertEqual(response.data["overallConfidence"], 0.86)
        self.assertEqual(response.data["createdById"], self.staff.id)
        self.assertEqual(len(response.data["findings"]), 1)
        self.assertEqual(response.data["findings"][0]["toothFdi"], "11")
        for field in (
            "clinicalDiagnosis",
            "finalDiagnosis",
            "diagnosis",
            "treatmentPlan",
            "prescription",
            "payment",
            "due",
            "dueAmount",
            "modelFilePath",
            "training",
        ):
            self.assertNotIn(field, response.data)

    def test_attachment_alias_and_findings_endpoint_return_stored_metadata_only(self):
        visit = self.make_visit_for_attachment("api-alias")
        attachment = self.make_attachment(visit.patient, visit=visit, uploaded_by=self.doctor)
        self.authenticate(self.staff)

        create_response = self.client.post(
            f"/api/attachments/{attachment.id}/ai-results/",
            self.ai_payload(
                attachment,
                attachmentId=999999,
                findings=[{"toothFdi": "21", "diseaseLabel": "Impacted", "confidence": 0.64}],
            ),
            format="json",
        )
        list_response = self.client.get(f"/api/attachments/{attachment.id}/ai-results/")
        latest_response = self.client.get(f"/api/attachments/{attachment.id}/ai-result/")
        findings_response = self.client.get(
            f"/api/ai-results/{create_response.data['id']}/findings/"
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["attachmentId"], attachment.id)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [create_response.data["id"]])
        self.assertEqual(latest_response.status_code, status.HTTP_200_OK)
        self.assertEqual(latest_response.data["id"], create_response.data["id"])
        self.assertEqual(findings_response.status_code, status.HTTP_200_OK)
        self.assertEqual(findings_response.data["results"][0]["diseaseLabel"], "Impacted")

    def test_doctor_can_create_and_read_only_own_active_visit_ai_results(self):
        own_visit = self.make_visit_for_attachment("api-doctor-own")
        own_attachment = self.make_attachment(
            own_visit.patient,
            visit=own_visit,
            uploaded_by=self.doctor,
        )
        other_visit = self.make_visit_for_attachment(
            "api-doctor-other",
            doctor_profile=self.other_doctor_profile,
        )
        other_attachment = self.make_attachment(
            other_visit.patient,
            visit=other_visit,
            uploaded_by=self.other_doctor,
        )
        patient_only = self.make_attachment(self.make_patient("api-patient-only"))
        other_result = self.make_ai_result(other_attachment, created_by=self.staff)
        patient_only_result = self.make_ai_result(patient_only, created_by=self.staff)
        self.authenticate(self.doctor)

        create_response = self.client.post(
            "/api/ai-results/",
            self.ai_payload(own_attachment, status_value=AIResult.Status.PROCESSING),
            format="json",
        )
        list_response = self.client.get("/api/ai-results/")
        own_response = self.client.get(f"/api/ai-results/{create_response.data['id']}/")
        other_response = self.client.get(f"/api/ai-results/{other_result.id}/")
        patient_only_response = self.client.get(f"/api/ai-results/{patient_only_result.id}/")
        other_create = self.client.post(
            "/api/ai-results/",
            self.ai_payload(other_attachment),
            format="json",
        )
        patient_only_create = self.client.post(
            "/api/ai-results/",
            self.ai_payload(patient_only),
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [create_response.data["id"]])
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patient_only_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(other_create.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patient_only_create.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_is_read_only_for_ai_results(self):
        visit = self.make_visit_for_attachment("api-admin")
        attachment = self.make_attachment(visit.patient, visit=visit)
        ai_result = self.make_ai_result(attachment, created_by=self.staff)
        self.authenticate(self.admin)

        list_response = self.client.get("/api/ai-results/")
        retrieve_response = self.client.get(f"/api/ai-results/{ai_result.id}/")
        create_response = self.client.post(
            "/api/ai-results/",
            self.ai_payload(attachment),
            format="json",
        )
        patch_response = self.client.patch(
            f"/api/ai-results/{ai_result.id}/",
            {"status": AIResult.Status.FAILED},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_patch_status_error_and_metadata_only(self):
        visit = self.make_visit_for_attachment("api-patch")
        attachment = self.make_attachment(visit.patient, visit=visit)
        ai_result = self.make_ai_result(
            attachment,
            status_value=AIResult.Status.PROCESSING,
            overall_confidence=None,
        )
        self.authenticate(self.staff)

        response = self.client.patch(
            f"/api/ai-results/{ai_result.id}/",
            {
                "status": AIResult.Status.FAILED,
                "errorMessage": "Stored import failed.",
                "metadata": {"review": "needed"},
            },
            format="json",
        )
        immutable_response = self.client.patch(
            f"/api/ai-results/{ai_result.id}/",
            {"modelVersion": "changed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], AIResult.Status.FAILED)
        self.assertEqual(response.data["errorMessage"], "Stored import failed.")
        self.assertEqual(response.data["metadata"], {"review": "needed"})
        self.assertEqual(immutable_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filters_support_attachment_patient_visit_status_model_and_created_range(self):
        visit = self.make_visit_for_attachment("api-filter")
        attachment = self.make_attachment(visit.patient, visit=visit)
        ai_result = self.make_ai_result(attachment, model_version="v-filter")
        other_patient = self.make_patient("api-filter-other")
        other_attachment = self.make_attachment(other_patient)
        other_result = self.make_ai_result(
            other_attachment,
            status_value=AIResult.Status.FAILED,
            model_version="v-other",
            overall_confidence=None,
        )
        date_from = timezone.now() - timedelta(minutes=10)
        date_to = timezone.now() + timedelta(minutes=10)
        self.authenticate(self.staff)

        responses = {
            "attachment": self.client.get("/api/ai-results/", {"attachmentId": attachment.id}),
            "patient": self.client.get("/api/ai-results/", {"patientId": visit.patient_id}),
            "visit": self.client.get("/api/ai-results/", {"visitId": visit.id}),
            "status": self.client.get("/api/ai-results/", {"status": AIResult.Status.FAILED}),
            "model": self.client.get("/api/ai-results/", {"modelVersion": "v-filter"}),
            "range": self.client.get(
                "/api/ai-results/",
                {"from": self.iso(date_from), "to": self.iso(date_to)},
            ),
        }

        self.assertEqual([item["id"] for item in responses["attachment"].data["results"]], [ai_result.id])
        self.assertEqual([item["id"] for item in responses["patient"].data["results"]], [ai_result.id])
        self.assertEqual([item["id"] for item in responses["visit"].data["results"]], [ai_result.id])
        self.assertEqual([item["id"] for item in responses["status"].data["results"]], [other_result.id])
        self.assertEqual([item["id"] for item in responses["model"].data["results"]], [ai_result.id])
        self.assertEqual(
            {item["id"] for item in responses["range"].data["results"]},
            {ai_result.id, other_result.id},
        )

    def test_validation_rejects_invalid_attachment_confidence_finding_and_fdi(self):
        visit = self.make_visit_for_attachment("api-validation")
        attachment = self.make_attachment(visit.patient, visit=visit)
        self.authenticate(self.staff)

        invalid_attachment = self.client.post(
            "/api/ai-results/",
            self.ai_payload(attachment, attachmentId=999999),
            format="json",
        )
        invalid_confidence = self.client.post(
            "/api/ai-results/",
            self.ai_payload(attachment, overall_confidence=1.01),
            format="json",
        )
        invalid_finding_confidence = self.client.post(
            "/api/ai-results/",
            self.ai_payload(
                attachment,
                findings=[{"toothFdi": "11", "diseaseLabel": "Caries", "confidence": 1.01}],
            ),
            format="json",
        )
        invalid_tooth = self.client.post(
            "/api/ai-results/",
            self.ai_payload(
                attachment,
                findings=[{"toothFdi": "19", "diseaseLabel": "Caries", "confidence": 0.5}],
            ),
            format="json",
        )

        self.assertEqual(invalid_attachment.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_confidence.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_finding_confidence.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_tooth.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_and_inactive_users_are_rejected(self):
        visit = self.make_visit_for_attachment("api-auth")
        attachment = self.make_attachment(visit.patient, visit=visit)

        anonymous_list = self.client.get("/api/ai-results/")
        anonymous_create = self.client.post(
            "/api/ai-results/",
            self.ai_payload(attachment),
            format="json",
        )
        self.authenticate(self.inactive)
        inactive_list = self.client.get("/api/ai-results/")
        inactive_create = self.client.post(
            "/api/ai-results/",
            self.ai_payload(attachment),
            format="json",
        )

        self.assertEqual(anonymous_list.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(anonymous_create.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(
            inactive_list.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            inactive_create.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_no_inference_training_endpoints_or_status_side_effects_exist(self):
        visit = self.make_visit_for_attachment("api-no-side-effects")
        attachment = self.make_attachment(visit.patient, visit=visit)
        appointment_status = visit.appointment.status
        appointment_version = visit.appointment.version
        visit_status = visit.status
        visit_version = visit.version
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/ai-results/",
            self.ai_payload(attachment),
            format="json",
        )
        missing_endpoint_responses = (
            self.client.post("/api/predict/", {}, format="json"),
            self.client.post("/api/infer/", {}, format="json"),
            self.client.post("/api/train/", {}, format="json"),
            self.client.post("/api/run-ai/", {}, format="json"),
            self.client.post("/api/analyze-xray/", {}, format="json"),
            self.client.post(f"/api/ai-results/{response.data['id']}/retry/", {}, format="json"),
        )
        visit.refresh_from_db()
        visit.appointment.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for missing_response in missing_endpoint_responses:
            self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(visit.status, visit_status)
        self.assertEqual(visit.version, visit_version)
        self.assertEqual(visit.appointment.status, appointment_status)
        self.assertEqual(visit.appointment.version, appointment_version)
        self.assertFalse(Invoice.objects.exists())

    def test_regression_core_backend_endpoints_still_work(self):
        visit = self.make_visit_for_attachment("api-regression")
        attachment = self.make_attachment(visit.patient, visit=visit)
        self.make_ai_result(attachment, created_by=self.staff)
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
            self.client.get("/api/invoices/"),
            self.client.get("/api/payments/"),
            self.client.get("/api/attachments/"),
            self.client.get("/api/ai-results/"),
        )

        self.assertTrue(apps.is_installed("ai_results"))
        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_no_ml_dependencies_were_added(self):
        with open("requirements.txt", encoding="utf-8") as requirements:
            requirement_text = requirements.read().lower()

        for forbidden in ("torch", "tensorflow", "ultralytics", "opencv", "numpy"):
            self.assertNotIn(forbidden, requirement_text)
