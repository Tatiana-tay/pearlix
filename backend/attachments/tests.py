import shutil
import tempfile
from datetime import timedelta, timezone as datetime_timezone

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from employees.models import EmployeeProfile
from scheduling.models import Appointment
from scheduling.test_appointments import AppointmentTestHelpers, BASE_AT
from visits.models import Visit

from .models import Attachment


class TempMediaMixin:
    @classmethod
    def setUpClass(cls):
        cls._temp_media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media_dir, ignore_errors=True)


class AttachmentTestHelpers(AppointmentTestHelpers):
    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def iso(self, value):
        return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")

    def upload_file(self, name="xray.jpg", content_type="image/jpeg", content=b"xray-bytes"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, content, content_type=content_type)

    def make_visit_for_attachment(
        self,
        suffix,
        *,
        doctor_profile=None,
        patient=None,
        status_value=Visit.Status.ACTIVE,
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

    def make_attachment(
        self,
        patient,
        *,
        visit=None,
        uploaded_by=None,
        name="xray.jpg",
        content_type="image/jpeg",
        attachment_type=Attachment.AttachmentType.XRAY,
        description="Initial upload",
    ):
        uploaded_file = self.upload_file(name=name, content_type=content_type)
        return Attachment.objects.create(
            patient=patient,
            visit=visit,
            uploaded_by=uploaded_by,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            content_type=uploaded_file.content_type,
            size_bytes=uploaded_file.size,
            attachment_type=attachment_type,
            description=description,
        )


class AttachmentModelTests(TempMediaMixin, AttachmentTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=3)
        User = get_user_model()
        self.doctor = self.make_user(User.Role.DOCTOR, "attachment-model-doctor@example.com")
        self.staff = self.make_user(User.Role.STAFF, "attachment-model-staff@example.com")
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-7100",
        )
        self.make_shift(self.doctor_profile)

    def test_attachment_can_store_patient_visit_uploader_and_metadata(self):
        visit = self.make_visit_for_attachment("model-create")

        attachment = self.make_attachment(
            visit.patient,
            visit=visit,
            uploaded_by=self.doctor,
            name="bitewing.png",
            content_type="image/png",
        )

        self.assertEqual(attachment.patient, visit.patient)
        self.assertEqual(attachment.visit, visit)
        self.assertEqual(attachment.uploaded_by, self.doctor)
        self.assertEqual(attachment.original_filename, "bitewing.png")
        self.assertEqual(attachment.content_type, "image/png")
        self.assertEqual(attachment.size_bytes, len(b"xray-bytes"))
        self.assertEqual(attachment.attachment_type, Attachment.AttachmentType.XRAY)
        self.assertFalse(attachment.is_deleted)

    def test_attachment_visit_must_match_patient(self):
        visit = self.make_visit_for_attachment("model-match")
        other_patient = self.make_patient("attachment-wrong-patient")

        with self.assertRaises(ValidationError):
            self.make_attachment(other_patient, visit=visit)

    def test_attachment_file_type_extension_and_size_are_validated(self):
        patient = self.make_patient("model-validation")

        for name, content_type in (
            ("malware.exe", "application/x-msdownload"),
            ("archive.zip", "application/zip"),
            ("mismatch.jpg", "image/png"),
            ("empty.jpg", "image/jpeg"),
        ):
            uploaded_file = self.upload_file(
                name=name,
                content_type=content_type,
                content=b"" if name == "empty.jpg" else b"content",
            )
            with self.assertRaises(ValidationError):
                Attachment.objects.create(
                    patient=patient,
                    file=uploaded_file,
                    original_filename=uploaded_file.name,
                    content_type=uploaded_file.content_type,
                    size_bytes=uploaded_file.size,
                )

        oversized = self.upload_file(
            content=b"x" * (Attachment.MAX_FILE_SIZE_BYTES + 1),
        )
        with self.assertRaises(ValidationError):
            Attachment.objects.create(
                patient=patient,
                file=oversized,
                original_filename=oversized.name,
                content_type=oversized.content_type,
                size_bytes=oversized.size,
            )

    def test_supported_dicom_placeholder_type_is_allowed(self):
        patient = self.make_patient("model-dicom")

        attachment = self.make_attachment(
            patient,
            name="panoramic.dcm",
            content_type="application/dicom",
        )

        self.assertEqual(attachment.content_type, "application/dicom")


class AttachmentAPITests(TempMediaMixin, AttachmentTestHelpers, APITestCase):
    def setUp(self):
        self.set_clinic(capacity=3)
        User = get_user_model()
        self.User = User
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.admin = self.make_user(
            User.Role.ADMIN,
            "admin-attachments@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.staff = self.make_user(User.Role.STAFF, "staff-attachments@example.com")
        self.doctor = self.make_user(User.Role.DOCTOR, "doctor-attachments@example.com")
        self.other_doctor = self.make_user(
            User.Role.DOCTOR,
            "other-doctor-attachments@example.com",
        )
        self.inactive = self.make_user(
            User.Role.DOCTOR,
            "inactive-attachments@example.com",
            user_status=User.Status.INACTIVE,
        )
        self.doctor_profile = EmployeeProfile.objects.create(
            user=self.doctor,
            specialty="Endodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-7200",
        )
        self.other_doctor_profile = EmployeeProfile.objects.create(
            user=self.other_doctor,
            specialty="Orthodontics",
            gender=EmployeeProfile.Gender.MALE,
            phone="+1-555-7201",
        )
        self.inactive_doctor_profile = EmployeeProfile.objects.create(
            user=self.inactive,
            specialty="Periodontics",
            gender=EmployeeProfile.Gender.FEMALE,
            phone="+1-555-7202",
        )
        self.make_shift(self.doctor_profile)
        self.make_shift(self.other_doctor_profile)

    def attachment_payload(
        self,
        *,
        patient,
        visit=None,
        name="xray.jpg",
        content_type="image/jpeg",
        attachment_type=Attachment.AttachmentType.XRAY,
        description="Initial X-ray upload",
        content=b"xray-bytes",
    ):
        payload = {
            "patientId": patient.id,
            "attachmentType": attachment_type,
            "description": description,
            "file": self.upload_file(
                name=name,
                content_type=content_type,
                content=content,
            ),
        }
        if visit is not None:
            payload["visitId"] = visit.id
        return payload

    def test_staff_can_upload_patient_only_attachment_and_response_shape(self):
        patient = self.make_patient("api-staff-upload")
        self.authenticate(self.staff)

        response = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=patient, name="bitewing.jpg"),
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["patientId"], patient.id)
        self.assertIsNone(response.data["visitId"])
        self.assertEqual(response.data["uploadedById"], self.staff.id)
        self.assertIn("uploadedByName", response.data)
        self.assertEqual(response.data["attachmentType"], Attachment.AttachmentType.XRAY)
        self.assertEqual(response.data["originalFilename"], "bitewing.jpg")
        self.assertEqual(response.data["contentType"], "image/jpeg")
        self.assertEqual(response.data["sizeBytes"], len(b"xray-bytes"))
        self.assertIn(f"/api/attachments/{response.data['id']}/original-url/", response.data["fileUrl"])
        self.assertFalse(response.data["isDeleted"])
        for field in (
            "filePath",
            "fileType",
            "aiResult",
            "aiResults",
            "aiFindings",
            "diagnosis",
            "due",
            "dueAmount",
            "paidAmount",
            "balance",
            "payment",
        ):
            self.assertNotIn(field, response.data)

        original_response = self.client.get(
            f"/api/attachments/{response.data['id']}/original-url/"
        )
        self.assertEqual(original_response.status_code, status.HTTP_200_OK)
        self.assertEqual(original_response["Content-Type"], "image/jpeg")

    def test_doctor_can_upload_only_for_own_active_visit(self):
        active_visit = self.make_visit_for_attachment("api-doctor-active")
        completed_visit = self.make_visit_for_attachment(
            "api-doctor-completed",
            status_value=Visit.Status.COMPLETED,
            start_at=BASE_AT + timedelta(hours=1),
        )
        self.authenticate(self.doctor)

        own_active = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=active_visit.patient, visit=active_visit),
            format="multipart",
        )
        patient_only = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=active_visit.patient),
            format="multipart",
        )
        completed = self.client.post(
            f"/api/visits/{completed_visit.id}/attachments/",
            self.attachment_payload(patient=completed_visit.patient),
            format="multipart",
        )

        self.assertEqual(own_active.status_code, status.HTTP_201_CREATED)
        self.assertEqual(own_active.data["visitId"], active_visit.id)
        self.assertEqual(patient_only.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(completed.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_access_other_doctor_or_patient_only_attachments(self):
        own_visit = self.make_visit_for_attachment("api-doctor-own")
        own_attachment = self.make_attachment(
            own_visit.patient,
            visit=own_visit,
            uploaded_by=self.doctor,
        )
        other_visit = self.make_visit_for_attachment(
            "api-doctor-other",
            doctor_profile=self.other_doctor_profile,
            start_at=BASE_AT,
        )
        other_attachment = self.make_attachment(
            other_visit.patient,
            visit=other_visit,
            uploaded_by=self.staff,
        )
        patient_only = self.make_attachment(
            self.make_patient("api-patient-only"),
            uploaded_by=self.staff,
        )
        self.authenticate(self.doctor)

        list_response = self.client.get("/api/attachments/")
        own_response = self.client.get(f"/api/attachments/{own_attachment.id}/")
        other_response = self.client.get(f"/api/attachments/{other_attachment.id}/")
        patient_only_response = self.client.get(f"/api/attachments/{patient_only.id}/")
        other_upload = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=other_visit.patient, visit=other_visit),
            format="multipart",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [own_attachment.id])
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patient_only_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(other_upload.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_read_update_metadata_and_soft_delete(self):
        patient = self.make_patient("api-staff-manage")
        attachment = self.make_attachment(patient, uploaded_by=self.staff)
        self.authenticate(self.staff)

        list_response = self.client.get("/api/attachments/")
        retrieve_response = self.client.get(f"/api/attachments/{attachment.id}/")
        patch_response = self.client.patch(
            f"/api/attachments/{attachment.id}/",
            {
                "attachmentType": Attachment.AttachmentType.DOCUMENT,
                "description": "Updated metadata only",
            },
            format="json",
        )
        file_patch = self.client.patch(
            f"/api/attachments/{attachment.id}/",
            {"file": self.upload_file()},
            format="multipart",
        )
        delete_response = self.client.delete(f"/api/attachments/{attachment.id}/")
        deleted_retrieve = self.client.get(f"/api/attachments/{attachment.id}/")
        deleted_list = self.client.get("/api/attachments/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [attachment.id])
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["attachmentType"], Attachment.AttachmentType.DOCUMENT)
        self.assertEqual(patch_response.data["description"], "Updated metadata only")
        self.assertEqual(file_patch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        attachment.refresh_from_db()
        self.assertTrue(attachment.is_deleted)
        self.assertEqual(deleted_retrieve.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(deleted_list.data["results"], [])

    def test_admin_is_read_only_for_attachments(self):
        patient = self.make_patient("api-admin-read")
        attachment = self.make_attachment(patient, uploaded_by=self.staff)
        self.authenticate(self.admin)

        list_response = self.client.get("/api/attachments/")
        retrieve_response = self.client.get(f"/api/attachments/{attachment.id}/")
        create_response = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=patient),
            format="multipart",
        )
        patch_response = self.client.patch(
            f"/api/attachments/{attachment.id}/",
            {"description": "Admin cannot update"},
            format="json",
        )
        delete_response = self.client.delete(f"/api/attachments/{attachment.id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filters_and_visit_attachment_alias(self):
        own_visit = self.make_visit_for_attachment("api-filter-own")
        own_attachment = self.make_attachment(
            own_visit.patient,
            visit=own_visit,
            uploaded_by=self.doctor,
        )
        document_patient = self.make_patient("api-filter-doc")
        document = self.make_attachment(
            document_patient,
            uploaded_by=self.staff,
            name="consent.pdf",
            content_type="application/pdf",
            attachment_type=Attachment.AttachmentType.DOCUMENT,
        )
        date_from = timezone.now() - timedelta(minutes=10)
        date_to = timezone.now() + timedelta(minutes=10)
        self.authenticate(self.staff)

        patient_response = self.client.get(
            "/api/attachments/",
            {"patientId": own_visit.patient_id},
        )
        visit_response = self.client.get(
            "/api/attachments/",
            {"visitId": own_visit.id},
        )
        type_response = self.client.get(
            "/api/attachments/",
            {"attachmentType": Attachment.AttachmentType.DOCUMENT},
        )
        uploader_response = self.client.get(
            "/api/attachments/",
            {"uploadedById": self.doctor.id},
        )
        range_response = self.client.get(
            "/api/attachments/",
            {
                "from": self.iso(date_from),
                "to": self.iso(date_to),
            },
        )
        alias_response = self.client.get(f"/api/visits/{own_visit.id}/attachments/")

        self.assertEqual([item["id"] for item in patient_response.data["results"]], [own_attachment.id])
        self.assertEqual([item["id"] for item in visit_response.data["results"]], [own_attachment.id])
        self.assertEqual([item["id"] for item in type_response.data["results"]], [document.id])
        self.assertEqual([item["id"] for item in uploader_response.data["results"]], [own_attachment.id])
        self.assertEqual(
            {item["id"] for item in range_response.data["results"]},
            {own_attachment.id, document.id},
        )
        self.assertEqual([item["id"] for item in alias_response.data["results"]], [own_attachment.id])

    def test_upload_validation_rejects_invalid_type_size_and_context(self):
        visit = self.make_visit_for_attachment("api-validation")
        other_patient = self.make_patient("api-validation-other")
        self.authenticate(self.staff)

        unsupported = self.client.post(
            "/api/attachments/",
            self.attachment_payload(
                patient=visit.patient,
                name="malware.exe",
                content_type="application/x-msdownload",
            ),
            format="multipart",
        )
        archive = self.client.post(
            "/api/attachments/",
            self.attachment_payload(
                patient=visit.patient,
                name="archive.zip",
                content_type="application/zip",
            ),
            format="multipart",
        )
        oversized = self.client.post(
            "/api/attachments/",
            self.attachment_payload(
                patient=visit.patient,
                content=b"x" * (Attachment.MAX_FILE_SIZE_BYTES + 1),
            ),
            format="multipart",
        )
        mismatch = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=other_patient, visit=visit),
            format="multipart",
        )
        missing_file = self.client.post(
            "/api/attachments/",
            {"patientId": visit.patient_id, "attachmentType": Attachment.AttachmentType.XRAY},
            format="multipart",
        )
        dicom = self.client.post(
            "/api/attachments/",
            self.attachment_payload(
                patient=visit.patient,
                name="scan.dcm",
                content_type="application/dicom",
            ),
            format="multipart",
        )

        self.assertEqual(unsupported.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(archive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(oversized.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_file.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(dicom.status_code, status.HTTP_201_CREATED)

    def test_anonymous_and_inactive_users_are_rejected(self):
        patient = self.make_patient("api-auth")

        anonymous_list = self.client.get("/api/attachments/")
        anonymous_create = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=patient),
            format="multipart",
        )
        self.authenticate(self.inactive)
        inactive_list = self.client.get("/api/attachments/")
        inactive_create = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=patient),
            format="multipart",
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

    def test_ai_storage_endpoints_exist_without_inference_or_visit_billing_side_effects(self):
        visit = self.make_visit_for_attachment("api-no-side-effects")
        appointment_status = visit.appointment.status
        appointment_version = visit.appointment.version
        visit_status = visit.status
        visit_version = visit.version
        self.authenticate(self.doctor)

        upload_response = self.client.post(
            "/api/attachments/",
            self.attachment_payload(patient=visit.patient, visit=visit),
            format="multipart",
        )
        ai_list_response = self.client.get("/api/ai-results/")
        ai_attachment_response = self.client.get(
            f"/api/attachments/{upload_response.data['id']}/ai-results/"
        )
        missing_inference_responses = (
            self.client.post("/api/predict/", {}, format="json"),
            self.client.post("/api/infer/", {}, format="json"),
            self.client.post("/api/train/", {}, format="json"),
            self.client.post("/api/run-ai/", {}, format="json"),
            self.client.post("/api/analyze-xray/", {}, format="json"),
        )
        appointment_response = self.client.get(f"/api/appointments/{visit.appointment_id}/")
        visit_response = self.client.get(f"/api/visits/{visit.id}/")
        visit.refresh_from_db()
        visit.appointment.refresh_from_db()

        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(apps.is_installed("ai_results"))
        self.assertEqual(ai_list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ai_attachment_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ai_list_response.data["results"], [])
        self.assertEqual(ai_attachment_response.data["results"], [])
        for missing_response in missing_inference_responses:
            self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(visit.status, visit_status)
        self.assertEqual(visit.version, visit_version)
        self.assertEqual(visit.appointment.status, appointment_status)
        self.assertEqual(visit.appointment.version, appointment_version)
        for response_data in (upload_response.data, appointment_response.data, visit_response.data):
            for field in (
                "aiResult",
                "aiResults",
                "aiFindings",
                "diagnosis",
                "due",
                "dueAmount",
                "paidAmount",
                "balance",
                "remainingBalance",
                "payment",
            ):
                self.assertNotIn(field, response_data)
