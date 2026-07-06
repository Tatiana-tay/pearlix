import shutil
import tempfile
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from ai_results.models import AIResult, AIResultFinding
from attachments.models import Attachment
from billing.models import Invoice, Payment
from employees.models import EmployeeProfile
from patients.models import Patient
from scheduling.models import Appointment, AvailabilityException, WorkingShift
from visits.models import Visit


class SeedDemoDataCommandTests(TestCase):
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

    def test_seed_demo_data_runs_and_is_idempotent(self):
        first_output = StringIO()
        call_command("seed_demo_data", stdout=first_output)
        first_counts = self.demo_counts()

        second_output = StringIO()
        call_command("seed_demo_data", stdout=second_output)
        second_counts = self.demo_counts()

        User = get_user_model()
        self.assertEqual(first_counts, second_counts)
        self.assertTrue(User.objects.filter(email="admin@example.com").exists())
        self.assertTrue(User.objects.filter(email="staff@example.com").exists())
        self.assertTrue(User.objects.filter(email="doctor@example.com").exists())
        self.assertTrue(
            EmployeeProfile.objects.filter(user__email="doctor@example.com").exists()
        )
        self.assertTrue(
            Patient.objects.filter(national_id_or_passport="DEMO-PAT-001").exists()
        )
        self.assertEqual(first_counts["doctor_profiles"], 4)
        self.assertEqual(first_counts["staff_profiles"], 2)
        self.assertEqual(first_counts["patients"], 24)
        self.assertGreaterEqual(first_counts["today_appointments"], 10)
        self.assertGreaterEqual(first_counts["future_appointments"], 16)
        self.assertGreaterEqual(first_counts["completed_visits"], 10)
        self.assertEqual(first_counts["active_visit_violations"], 0)
        self.assertEqual(first_counts["pending_invoices"], 3)
        self.assertEqual(first_counts["partial_invoices"], 3)
        self.assertEqual(first_counts["paid_invoices"], 3)
        self.assertEqual(first_counts["cancelled_invoices"], 1)
        self.assertGreaterEqual(first_counts["payments"], 6)
        self.assertEqual(first_counts["attachments"], 8)
        self.assertGreaterEqual(first_counts["completed_ai_results"], 4)
        self.assertGreaterEqual(first_counts["processing_ai_results"], 1)
        self.assertGreaterEqual(first_counts["failed_ai_results"], 1)
        self.assertGreaterEqual(first_counts["ai_findings"], 8)
        self.assert_demo_files_exist()
        self.assertIn("patients:", second_output.getvalue())

    def test_seed_dev_users_still_works(self):
        call_command("seed_dev_users", stdout=StringIO())

        User = get_user_model()
        staff = User.objects.get(email="staff@example.com")
        inactive = User.objects.get(email="inactive@example.com")
        self.assertEqual(staff.role, User.Role.STAFF)
        self.assertTrue(staff.check_password("Staff123!"))
        self.assertEqual(inactive.status, User.Status.INACTIVE)

    def demo_counts(self):
        today = timezone.localdate()
        return {
            "doctor_profiles": EmployeeProfile.objects.filter(
                user__email__in=[
                    "doctor@example.com",
                    "demo.doctor.ortho@example.com",
                    "demo.doctor.surgery@example.com",
                    "demo.doctor.endo@example.com",
                ],
                user__role=get_user_model().Role.DOCTOR,
            ).count(),
            "staff_profiles": EmployeeProfile.objects.filter(
                user__email__in=["staff@example.com", "demo.staff.reception@example.com"],
                user__role=get_user_model().Role.STAFF,
            ).count(),
            "shifts": WorkingShift.objects.filter(
                employee_profile__user__email__in=[
                    "doctor@example.com",
                    "demo.doctor.ortho@example.com",
                    "demo.doctor.surgery@example.com",
                    "demo.doctor.endo@example.com",
                ]
            ).count(),
            "leave": AvailabilityException.objects.filter(
                note__startswith="DEMO-SEED"
            ).count(),
            "patients": Patient.objects.filter(
                national_id_or_passport__startswith="DEMO-PAT-"
            ).count(),
            "appointments": Appointment.objects.filter(
                notes__startswith="DEMO-SEED"
            ).count(),
            "today_appointments": Appointment.objects.filter(
                notes__startswith="DEMO-SEED: today-"
            ).count(),
            "future_appointments": Appointment.objects.filter(
                notes__startswith="DEMO-SEED: future-",
                start_at__date__gte=today,
            ).count(),
            "completed_visits": Visit.objects.filter(
                general_notes__startswith="DEMO-SEED"
            ).filter(status=Visit.Status.COMPLETED).count(),
            "active_visit_violations": sum(
                1
                for doctor_id in Visit.objects.filter(status=Visit.Status.ACTIVE)
                .values_list("doctor_profile_id", flat=True)
                .distinct()
                if Visit.objects.filter(
                    status=Visit.Status.ACTIVE,
                    doctor_profile_id=doctor_id,
                ).count()
                > 1
            ),
            "pending_invoices": Invoice.objects.filter(
                note__startswith="DEMO-SEED",
                status=Invoice.Status.PENDING,
            ).count(),
            "partial_invoices": Invoice.objects.filter(
                note__startswith="DEMO-SEED",
                status=Invoice.Status.PARTIALLY_PAID,
            ).count(),
            "paid_invoices": Invoice.objects.filter(
                note__startswith="DEMO-SEED",
                status=Invoice.Status.PAID,
            ).count(),
            "cancelled_invoices": Invoice.objects.filter(
                note__startswith="DEMO-SEED",
                status=Invoice.Status.CANCELLED,
            ).count(),
            "payments": Payment.objects.filter(note__startswith="DEMO-SEED").count(),
            "attachments": Attachment.objects.filter(
                original_filename__startswith="demo_xray_patient_",
                description__startswith="DEMO-SEED",
            ).count(),
            "completed_ai_results": AIResult.objects.filter(
                model_version__startswith="demo-seed-completed-",
                status=AIResult.Status.COMPLETED,
            ).count(),
            "processing_ai_results": AIResult.objects.filter(
                model_version="demo-seed-processing",
                status=AIResult.Status.PROCESSING,
            ).count(),
            "failed_ai_results": AIResult.objects.filter(
                model_version="demo-seed-failed",
                status=AIResult.Status.FAILED,
            ).count(),
            "ai_findings": AIResultFinding.objects.filter(
                ai_result__model_version__startswith="demo-seed-completed-"
            ).count(),
        }

    def assert_demo_files_exist(self):
        for attachment in Attachment.objects.filter(
            original_filename__startswith="demo_xray_patient_",
            description__startswith="DEMO-SEED",
        ):
            self.assertTrue(attachment.file.storage.exists(attachment.file.name))
