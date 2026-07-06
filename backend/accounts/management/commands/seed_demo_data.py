from datetime import date, datetime, time, timedelta
from decimal import Decimal
import base64
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ai_results.models import AIResult, AIResultFinding
from attachments.models import Attachment
from billing.models import Invoice, InvoiceAuditLog, Payment
from core.models import ClinicSettings
from employees.models import EmployeeProfile
from patients.models import Patient
from scheduling.models import (
    Appointment,
    AppointmentChangeLog,
    AvailabilityException,
    WorkingShift,
)
from visits.models import Visit


DEMO_PREFIX = "DEMO-SEED"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class Command(BaseCommand):
    help = "Seed idempotent demo data for frontend manual testing."

    def handle(self, *args, **options):
        self.summary = {}

        with transaction.atomic():
            call_command("seed_dev_users", verbosity=0)
            users = self.ensure_users()
            profiles = self.ensure_profiles(users)
            self.ensure_working_shifts(profiles["doctor"])
            base_date = self.demo_week_start(profiles["doctor"])
            self.ensure_leave(profiles["doctor"], users["admin"], base_date)
            patients = self.ensure_patients()
            appointments = self.ensure_appointments(
                patients,
                profiles["doctor"],
                users["staff"],
                base_date,
            )
            visits = self.ensure_visits(appointments, profiles["doctor"])
            invoices = self.ensure_billing(visits, users["doctor"], users["staff"])
            attachment = self.ensure_attachment(
                visits["completed_partial"].patient,
                visits["completed_partial"],
                users["staff"],
            )
            self.ensure_ai_results(attachment, users["doctor"])

        self.print_summary()

    def count(self, key, created):
        bucket = self.summary.setdefault(key, {"created": 0, "updated": 0})
        bucket["created" if created else "updated"] += 1

    def ensure_users(self):
        User = get_user_model()
        demo_doctor, created = User.objects.update_or_create(
            username="demo.doctor@example.com",
            defaults={
                "email": "demo.doctor@example.com",
                "full_name": "Demo Doctor Extra",
                "role": User.Role.DOCTOR,
                "status": User.Status.ACTIVE,
                "must_change_password": False,
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
            },
        )
        demo_doctor.set_password("DemoDoctor123!")
        demo_doctor.save()
        self.count("users", created)

        users = {
            "admin": User.objects.get(email="admin@example.com"),
            "staff": User.objects.get(email="staff@example.com"),
            "doctor": User.objects.get(email="doctor@example.com"),
            "demo_doctor": demo_doctor,
        }
        for key in ("admin", "staff", "doctor"):
            self.count("users", False)
        return users

    def ensure_profiles(self, users):
        values = {
            "doctor": {
                "user": users["doctor"],
                "specialty": "Restorative Dentistry",
                "gender": EmployeeProfile.Gender.MALE,
                "phone": "+1-555-0103",
            },
            "staff": {
                "user": users["staff"],
                "specialty": "",
                "gender": EmployeeProfile.Gender.FEMALE,
                "phone": "+1-555-0102",
            },
            "demo_doctor": {
                "user": users["demo_doctor"],
                "specialty": "Orthodontics",
                "gender": EmployeeProfile.Gender.FEMALE,
                "phone": "+1-555-0104",
            },
        }
        profiles = {}
        for key, data in values.items():
            user = data.pop("user")
            profile, created = EmployeeProfile.objects.update_or_create(
                user=user,
                defaults=data,
            )
            profiles[key] = profile
            self.count("employee profiles", created)
        return profiles

    def ensure_working_shifts(self, doctor_profile):
        weekdays = [
            WorkingShift.DayOfWeek.MONDAY,
            WorkingShift.DayOfWeek.TUESDAY,
            WorkingShift.DayOfWeek.WEDNESDAY,
            WorkingShift.DayOfWeek.THURSDAY,
            WorkingShift.DayOfWeek.FRIDAY,
        ]
        today_name = timezone.localdate().strftime("%A")
        if today_name not in weekdays:
            weekdays.append(WorkingShift.DayOfWeek(today_name))

        for weekday in weekdays:
            covering_shift = WorkingShift.objects.filter(
                employee_profile=doctor_profile,
                day_of_week=weekday,
                is_active=True,
                start_time__lte=time(9, 0),
                end_time__gte=time(17, 0),
            ).first()
            if covering_shift:
                self.count("working shifts", False)
                continue

            overlapping_shift = WorkingShift.objects.filter(
                employee_profile=doctor_profile,
                day_of_week=weekday,
                is_active=True,
                start_time__lt=time(17, 0),
                end_time__gt=time(9, 0),
            ).first()
            if overlapping_shift:
                overlapping_shift.start_time = min(overlapping_shift.start_time, time(9, 0))
                overlapping_shift.end_time = max(overlapping_shift.end_time, time(17, 0))
                overlapping_shift.save()
                self.count("working shifts", False)
                continue

            shift, created = WorkingShift.objects.update_or_create(
                employee_profile=doctor_profile,
                day_of_week=weekday,
                start_time=time(9, 0),
                defaults={"end_time": time(17, 0), "is_active": True},
            )
            self.count("working shifts", created)
            if shift.end_time != time(17, 0) or not shift.is_active:
                shift.end_time = time(17, 0)
                shift.is_active = True
                shift.save()

    def demo_week_start(self, doctor_profile):
        existing_demo = (
            Appointment.objects.filter(
                doctor_profile=doctor_profile,
                notes__startswith=DEMO_PREFIX,
            )
            .order_by("start_at")
            .first()
        )
        if existing_demo:
            settings = ClinicSettings.get_solo()
            clinic_tz = ZoneInfo(settings.clinic_timezone)
            local_date = existing_demo.start_at.astimezone(clinic_tz).date()
            return local_date - timedelta(days=local_date.weekday())

        local_today = timezone.localdate()
        days_until_monday = (0 - local_today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        candidate = local_today + timedelta(days=days_until_monday)
        for week in range(24):
            start = candidate + timedelta(weeks=week)
            if self.week_has_open_demo_slots(doctor_profile, start):
                return start
        return candidate + timedelta(weeks=24)

    def week_has_open_demo_slots(self, doctor_profile, monday):
        starts = [self.local_dt(monday, 9 + idx, 0) for idx in range(8)]
        for start_at in starts:
            end_at = start_at + timedelta(minutes=45)
            if Appointment.objects.filter(
                doctor_profile=doctor_profile,
                status__in=Appointment.BLOCKING_STATUSES,
                start_at__lt=end_at,
                end_at__gt=start_at,
            ).exists():
                return False
            if AvailabilityException.objects.filter(
                employee_profile=doctor_profile,
                status=AvailabilityException.Status.ACTIVE,
                start_at__lt=end_at,
                end_at__gt=start_at,
            ).exists():
                return False
        return True

    def local_dt(self, target_date, hour, minute):
        settings = ClinicSettings.get_solo()
        clinic_tz = ZoneInfo(settings.clinic_timezone)
        return datetime.combine(target_date, time(hour, minute), tzinfo=clinic_tz)

    def ensure_leave(self, doctor_profile, admin_user, monday):
        friday = monday + timedelta(days=4)
        note = f"{DEMO_PREFIX}: short future training block"
        existing = AvailabilityException.objects.filter(
            employee_profile=doctor_profile,
            note=note,
        ).order_by("id")
        leave = existing.first()
        created = leave is None
        if leave is None:
            leave = AvailabilityException(employee_profile=doctor_profile, note=note)

        if existing.count() > 1:
            existing.exclude(pk=leave.pk).delete()

        leave.start_at = self.local_dt(friday, 15, 0)
        leave.end_at = self.local_dt(friday, 16, 0)
        leave.reason = AvailabilityException.Reason.TRAINING
        leave.status = AvailabilityException.Status.ACTIVE
        leave.created_by = admin_user
        leave.save()
        self.count("leave/availability", created)
        return leave

    def ensure_patients(self):
        rows = [
            ("One", Patient.Gender.FEMALE, date(1991, 4, 12), "A+"),
            ("Two", Patient.Gender.MALE, date(1984, 8, 3), "O+"),
            ("Three", Patient.Gender.FEMALE, date(2002, 2, 20), "B+"),
            ("Four", Patient.Gender.MALE, date(1976, 11, 9), "AB+"),
            ("Five", Patient.Gender.FEMALE, date(1999, 6, 1), "O-"),
            ("Six", Patient.Gender.MALE, date(1968, 12, 18), "A-"),
            ("Seven", Patient.Gender.FEMALE, date(2010, 5, 24), "B-"),
            ("Eight", Patient.Gender.MALE, date(1994, 9, 14), "AB-"),
            ("Nine", Patient.Gender.FEMALE, date(1988, 1, 30), "A+"),
            ("Ten", Patient.Gender.MALE, date(2005, 7, 7), "O+"),
        ]
        patients = []
        for idx, (name, gender, dob, blood_group) in enumerate(rows, start=1):
            patient, created = Patient.objects.update_or_create(
                national_id_or_passport=f"DEMO-PAT-{idx:03d}",
                defaults={
                    "first_name": "Demo Patient",
                    "last_name": name,
                    "gender": gender,
                    "date_of_birth": dob,
                    "phone_number": f"+1-555-20{idx:02d}",
                    "email": f"demo.patient.{idx}@example.com",
                    "address": f"{idx} Demo Clinic Street",
                    "medical_conditions_history": "Demo-only dental history notes.",
                    "blood_group": blood_group,
                    "insurance_info": f"Demo Insurance Plan {idx}",
                    "emergency_contact": f"Demo Contact {idx} +1-555-30{idx:02d}",
                },
            )
            patients.append(patient)
            self.count("patients", created)
        return patients

    def ensure_appointments(self, patients, doctor_profile, staff_user, monday):
        active_visit_conflict = (
            Visit.objects.filter(
                doctor_profile=doctor_profile,
                status=Visit.Status.ACTIVE,
            )
            .exclude(appointment__notes=f"{DEMO_PREFIX}: in-visit")
            .exists()
        )
        specs = [
            ("scheduled", Appointment.Status.SCHEDULED, 9, Appointment.VisitType.ROUTINE_CHECKUP),
            ("arrived", Appointment.Status.ARRIVED, 10, Appointment.VisitType.INITIAL_CONSULTATION),
            ("checked-in", Appointment.Status.CHECKED_IN, 11, Appointment.VisitType.CLEANING_VISIT),
            ("in-visit", Appointment.Status.IN_VISIT, 12, Appointment.VisitType.TREATMENT_CONTINUATION),
            ("completed-pending", Appointment.Status.COMPLETED, 13, Appointment.VisitType.FOLLOW_UP_VISIT),
            ("completed-partial", Appointment.Status.COMPLETED, 14, Appointment.VisitType.X_RAY_REVIEW),
            ("completed-paid", Appointment.Status.COMPLETED, 15, Appointment.VisitType.POST_TREATMENT_REVIEW),
            ("completed-cancelled", Appointment.Status.COMPLETED, 16, Appointment.VisitType.EMERGENCY_VISIT),
            ("cancelled", Appointment.Status.CANCELLED, 9, Appointment.VisitType.ROUTINE_CHECKUP),
            ("no-show", Appointment.Status.NO_SHOW, 10, Appointment.VisitType.ROUTINE_CHECKUP),
            ("postponed", Appointment.Status.POSTPONED, 11, Appointment.VisitType.ROUTINE_CHECKUP),
            ("needs-reschedule", Appointment.Status.NEEDS_RESCHEDULE, 12, Appointment.VisitType.ROUTINE_CHECKUP),
        ]
        appointments = {}
        for idx, (key, status, hour, visit_type) in enumerate(specs):
            if key == "in-visit" and active_visit_conflict:
                status = Appointment.Status.CHECKED_IN
            day = monday if idx < 8 else monday + timedelta(days=1)
            start_at = self.local_dt(day, hour, 0)
            note = f"{DEMO_PREFIX}: {key}"
            appointment, created = Appointment.objects.update_or_create(
                notes=note,
                defaults={
                    "patient": patients[idx % len(patients)],
                    "doctor_profile": doctor_profile,
                    "start_at": start_at,
                    "end_at": start_at + timedelta(minutes=45),
                    "duration_minutes": 45,
                    "visit_type": visit_type,
                    "status": status,
                    "created_by": staff_user,
                },
            )
            appointments[key] = appointment
            self.count("appointments", created)
            self.ensure_appointment_log(appointment, status, staff_user)
        return appointments

    def ensure_appointment_log(self, appointment, status, user):
        action_by_status = {
            Appointment.Status.ARRIVED: AppointmentChangeLog.Action.ARRIVE,
            Appointment.Status.CHECKED_IN: AppointmentChangeLog.Action.CHECK_IN,
            Appointment.Status.IN_VISIT: AppointmentChangeLog.Action.START_VISIT,
            Appointment.Status.COMPLETED: AppointmentChangeLog.Action.COMPLETE_VISIT,
            Appointment.Status.CANCELLED: AppointmentChangeLog.Action.CANCEL,
            Appointment.Status.NO_SHOW: AppointmentChangeLog.Action.MARK_NO_SHOW,
            Appointment.Status.POSTPONED: AppointmentChangeLog.Action.POSTPONE,
            Appointment.Status.NEEDS_RESCHEDULE: AppointmentChangeLog.Action.MARK_NEEDS_RESCHEDULE,
        }
        action = action_by_status.get(status)
        if not action:
            return
        _, created = AppointmentChangeLog.objects.get_or_create(
            appointment=appointment,
            action=action,
            reason=f"{DEMO_PREFIX}: seeded workflow history",
            defaults={
                "previous_status": Appointment.Status.SCHEDULED,
                "new_status": status,
                "changed_by": user,
                "note": "Demo workflow state",
                "metadata": {"seed": "seed_demo_data"},
            },
        )
        self.count("appointment logs", created)

    def ensure_visits(self, appointments, doctor_profile):
        visits = {}
        visit_specs = {
            "active": ("in-visit", Visit.Status.ACTIVE),
            "completed_pending": ("completed-pending", Visit.Status.COMPLETED),
            "completed_partial": ("completed-partial", Visit.Status.COMPLETED),
            "completed_paid": ("completed-paid", Visit.Status.COMPLETED),
            "completed_cancelled": ("completed-cancelled", Visit.Status.COMPLETED),
        }
        for key, (appointment_key, status) in visit_specs.items():
            appointment = appointments[appointment_key]
            existing_active = Visit.objects.filter(
                doctor_profile=doctor_profile,
                status=Visit.Status.ACTIVE,
            ).exclude(appointment=appointment).first()
            if status == Visit.Status.ACTIVE and existing_active:
                if appointment.status == Appointment.Status.IN_VISIT:
                    appointment.status = Appointment.Status.CHECKED_IN
                    appointment.save(update_fields=["status", "updated_at"])
                    AppointmentChangeLog.objects.filter(
                        appointment=appointment,
                        action=AppointmentChangeLog.Action.START_VISIT,
                        reason=f"{DEMO_PREFIX}: seeded workflow history",
                    ).delete()
                    self.ensure_appointment_log(
                        appointment,
                        Appointment.Status.CHECKED_IN,
                        appointment.created_by,
                    )
                visits[key] = existing_active
                self.count("visits", False)
                continue
            defaults = {
                "patient": appointment.patient,
                "doctor_profile": appointment.doctor_profile,
                "status": status,
                "subjective_notes": f"{DEMO_PREFIX}: subjective demo notes",
                "objective_notes": f"{DEMO_PREFIX}: objective demo notes",
                "assessment_notes": f"{DEMO_PREFIX}: assessment demo notes",
                "plan_notes": f"{DEMO_PREFIX}: plan demo notes",
                "general_notes": f"{DEMO_PREFIX}: general demo notes",
                "started_at": appointment.start_at,
                "completed_at": appointment.end_at if status == Visit.Status.COMPLETED else None,
            }
            visit, created = Visit.objects.update_or_create(
                appointment=appointment,
                defaults=defaults,
            )
            visits[key] = visit
            self.count("visits", created)
        return visits

    def ensure_billing(self, visits, doctor_user, staff_user):
        invoice_specs = {
            "pending": ("completed_pending", "180.00", Invoice.Status.PENDING, []),
            "partial": ("completed_partial", "240.00", Invoice.Status.PENDING, ["100.00"]),
            "paid": ("completed_paid", "150.00", Invoice.Status.PENDING, ["150.00"]),
            "cancelled": ("completed_cancelled", "90.00", Invoice.Status.CANCELLED, []),
        }
        invoices = {}
        for key, (visit_key, amount, status, payments) in invoice_specs.items():
            visit = visits[visit_key]
            invoice, created = Invoice.objects.update_or_create(
                visit=visit,
                defaults={
                    "patient": visit.patient,
                    "doctor_profile": visit.doctor_profile,
                    "created_by": doctor_user,
                    "total_amount": Decimal(amount),
                    "status": status,
                    "note": f"{DEMO_PREFIX}: {key} invoice",
                },
            )
            self.count("invoices", created)
            for payment_amount in payments:
                self.ensure_payment(invoice, payment_amount, staff_user)
            if status != Invoice.Status.CANCELLED:
                invoice.status = invoice.calculated_status
                invoice.save(update_fields=["status", "updated_at"])
            else:
                self.ensure_invoice_cancel_log(invoice, staff_user)
            invoices[key] = invoice
        return invoices

    def ensure_payment(self, invoice, amount, staff_user):
        _, created = Payment.objects.update_or_create(
            invoice=invoice,
            note=f"{DEMO_PREFIX}: Cash payment {amount}",
            defaults={
                "amount": Decimal(amount),
                "method": Payment.Method.CASH,
                "received_by": staff_user,
            },
        )
        self.count("payments", created)

    def ensure_invoice_cancel_log(self, invoice, staff_user):
        _, created = InvoiceAuditLog.objects.get_or_create(
            invoice=invoice,
            action=InvoiceAuditLog.Action.CANCEL,
            reason=f"{DEMO_PREFIX}: seeded cancelled invoice",
            defaults={
                "previous_total": invoice.total_amount,
                "new_total": invoice.total_amount,
                "previous_status": Invoice.Status.PENDING,
                "new_status": Invoice.Status.CANCELLED,
                "changed_by": staff_user,
            },
        )
        self.count("invoice logs", created)

    def ensure_attachment(self, patient, visit, staff_user):
        attachment = Attachment.objects.filter(
            patient=patient,
            visit=visit,
            original_filename="demo-seed-xray.png",
            is_deleted=False,
        ).first()
        created = attachment is None
        if attachment is None:
            attachment = Attachment(
                patient=patient,
                visit=visit,
                uploaded_by=staff_user,
                original_filename="demo-seed-xray.png",
                content_type="image/png",
                size_bytes=len(PNG_BYTES),
                attachment_type=Attachment.AttachmentType.XRAY,
                description=f"{DEMO_PREFIX}: tiny demo X-ray image",
            )
            attachment.file.save(
                "demo-seed-xray.png",
                ContentFile(PNG_BYTES),
                save=False,
            )
        else:
            attachment.uploaded_by = staff_user
            attachment.content_type = "image/png"
            attachment.size_bytes = len(PNG_BYTES)
            attachment.attachment_type = Attachment.AttachmentType.XRAY
            attachment.description = f"{DEMO_PREFIX}: tiny demo X-ray image"
            if not attachment.file or not attachment.file.storage.exists(attachment.file.name):
                attachment.file.save(
                    "demo-seed-xray.png",
                    ContentFile(PNG_BYTES),
                    save=False,
                )
        attachment.save()
        self.count("attachments", created)
        return attachment

    def ensure_ai_results(self, attachment, doctor_user):
        specs = [
            (
                "completed",
                AIResult.Status.COMPLETED,
                "Demo completed findings for frontend review.",
                0.76,
                "",
            ),
            ("processing", AIResult.Status.PROCESSING, "Demo result still processing.", None, ""),
            ("failed", AIResult.Status.FAILED, "", None, "Demo failure for error-state testing."),
        ]
        for key, status, summary, confidence, error in specs:
            result, created = AIResult.objects.update_or_create(
                attachment=attachment,
                model_name="Demo Stored AI Result",
                model_version=f"demo-seed-{key}",
                defaults={
                    "patient": attachment.patient,
                    "visit": attachment.visit,
                    "status": status,
                    "result_summary": summary,
                    "overall_confidence": confidence,
                    "overlay_url": "",
                    "error_message": error,
                    "metadata": {"seed": "seed_demo_data", "demoOnly": True},
                    "created_by": doctor_user,
                },
            )
            self.count("AI results", created)
            if status == AIResult.Status.COMPLETED:
                self.ensure_ai_finding(result, "36", "Caries", 0.82)
                self.ensure_ai_finding(result, "46", "Periapical Lesion", 0.64)
        return None

    def ensure_ai_finding(self, ai_result, tooth_fdi, disease_label, confidence):
        _, created = AIResultFinding.objects.update_or_create(
            ai_result=ai_result,
            tooth_fdi=tooth_fdi,
            disease_label=disease_label,
            defaults={
                "confidence": confidence,
                "bbox": {"x": 0.12, "y": 0.18, "width": 0.2, "height": 0.16},
                "mask": None,
                "metadata": {"seed": "seed_demo_data", "demoOnly": True},
            },
        )
        self.count("AI findings", created)

    def print_summary(self):
        for key in sorted(self.summary):
            counts = self.summary[key]
            self.stdout.write(
                self.style.SUCCESS(
                    f"{key}: {counts['created']} created, {counts['updated']} updated"
                )
            )
