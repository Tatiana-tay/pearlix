import shutil
import tempfile
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

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
        self.assertEqual(first_counts["patients"], 10)
        self.assertEqual(first_counts["appointments"], 12)
        self.assertEqual(first_counts["leave"], 1)
        self.assertEqual(first_counts["invoices"], 4)
        self.assertEqual(first_counts["payments"], 2)
        self.assertEqual(first_counts["attachments"], 1)
        self.assertEqual(first_counts["ai_results"], 3)
        self.assertEqual(first_counts["ai_findings"], 2)
        self.assertTrue(
            Attachment.objects.get(
                original_filename="demo-seed-xray.png",
                description__startswith="DEMO-SEED",
            ).file.storage.exists(
                Attachment.objects.get(
                    original_filename="demo-seed-xray.png",
                    description__startswith="DEMO-SEED",
                ).file.name
            )
        )
        self.assertIn("patients:", second_output.getvalue())

    def test_seed_dev_users_still_works(self):
        call_command("seed_dev_users", stdout=StringIO())

        User = get_user_model()
        staff = User.objects.get(email="staff@example.com")
        self.assertEqual(staff.role, User.Role.STAFF)
        self.assertTrue(staff.check_password("Staff123!"))

    def demo_counts(self):
        return {
            "demo_doctor_users": get_user_model().objects.filter(
                email="demo.doctor@example.com"
            ).count(),
            "profiles": EmployeeProfile.objects.filter(
                user__email__in=[
                    "staff@example.com",
                    "doctor@example.com",
                    "demo.doctor@example.com",
                ]
            ).count(),
            "shifts": WorkingShift.objects.filter(
                employee_profile__user__email="doctor@example.com"
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
            "visits": Visit.objects.filter(
                general_notes__startswith="DEMO-SEED"
            ).count(),
            "invoices": Invoice.objects.filter(note__startswith="DEMO-SEED").count(),
            "payments": Payment.objects.filter(note__startswith="DEMO-SEED").count(),
            "attachments": Attachment.objects.filter(
                original_filename="demo-seed-xray.png",
                description__startswith="DEMO-SEED",
            ).count(),
            "ai_results": AIResult.objects.filter(
                model_version__startswith="demo-seed-"
            ).count(),
            "ai_findings": AIResultFinding.objects.filter(
                ai_result__model_version="demo-seed-completed"
            ).count(),
        }
