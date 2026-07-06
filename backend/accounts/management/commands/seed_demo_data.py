from datetime import date, datetime, time, timedelta
from decimal import Decimal
import base64
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
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
    help = "Seed idempotent scenario demo data for frontend manual testing."

    def handle(self, *args, **options):
        self.summary = {}

        with transaction.atomic():
            call_command("seed_dev_users", verbosity=0)
            users = self.ensure_users()
            profiles = self.ensure_profiles(users)
            self.ensure_working_shifts(profiles)
            dates = self.demo_dates()
            self.ensure_leave_blocks(profiles, users["admin"], dates)
            patients = self.ensure_patients()
            appointments = self.ensure_appointments(patients, profiles, users["staff"], dates)
            visits = self.ensure_visits(appointments, profiles["doctor"])
            invoices = self.ensure_billing(visits, users["doctor"], users["staff"])
            attachments = self.ensure_attachments(patients, visits, users["staff"])
            self.ensure_ai_results(attachments, users["doctor"])

        self.print_summary()

    def count(self, key, created):
        bucket = self.summary.setdefault(key, {"created": 0, "updated": 0})
        bucket["created" if created else "updated"] += 1

    def ensure_users(self):
        User = get_user_model()
        specs = {
            "admin": ("admin@example.com", None, "Admin User", User.Role.ADMIN, True, True),
            "staff": ("staff@example.com", None, "Staff User", User.Role.STAFF, False, False),
            "doctor": ("doctor@example.com", None, "Doctor User", User.Role.DOCTOR, False, False),
            "ortho": (
                "demo.doctor.ortho@example.com",
                "DemoOrtho123!",
                "Demo Ortho Doctor",
                User.Role.DOCTOR,
                False,
                False,
            ),
            "surgery": (
                "demo.doctor.surgery@example.com",
                "DemoSurgery123!",
                "Demo Surgery Doctor",
                User.Role.DOCTOR,
                False,
                False,
            ),
            "endo": (
                "demo.doctor.endo@example.com",
                "DemoEndo123!",
                "Demo Endo Doctor",
                User.Role.DOCTOR,
                False,
                False,
            ),
            "reception": (
                "demo.staff.reception@example.com",
                "DemoReception123!",
                "Demo Reception Staff",
                User.Role.STAFF,
                False,
                False,
            ),
        }
        users = {}
        for key, (email, password, full_name, role, is_staff, is_superuser) in specs.items():
            user, created = User.objects.update_or_create(
                username=email,
                defaults={
                    "email": email,
                    "full_name": full_name,
                    "role": role,
                    "status": User.Status.ACTIVE,
                    "must_change_password": False,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                    "is_active": True,
                },
            )
            if password:
                user.set_password(password)
                user.save(update_fields=["password"])
            users[key] = user
            self.count("users", created)
        return users

    def ensure_profiles(self, users):
        values = {
            "doctor": (users["doctor"], "Restorative Dentistry", EmployeeProfile.Gender.MALE, "+1-555-0103"),
            "ortho": (users["ortho"], "Orthodontics", EmployeeProfile.Gender.FEMALE, "+1-555-0104"),
            "surgery": (users["surgery"], "Oral Surgery", EmployeeProfile.Gender.MALE, "+1-555-0105"),
            "endo": (users["endo"], "Endodontics", EmployeeProfile.Gender.FEMALE, "+1-555-0106"),
            "staff": (users["staff"], "", EmployeeProfile.Gender.FEMALE, "+1-555-0102"),
            "reception": (users["reception"], "", EmployeeProfile.Gender.FEMALE, "+1-555-0107"),
        }
        profiles = {}
        for key, (user, specialty, gender, phone) in values.items():
            profile, created = EmployeeProfile.objects.update_or_create(
                user=user,
                defaults={"specialty": specialty, "gender": gender, "phone": phone},
            )
            profiles[key] = profile
            self.count("employee profiles", created)
        return profiles

    def ensure_working_shifts(self, profiles):
        weekday_sets = {
            "doctor": (
                [WorkingShift.DayOfWeek.MONDAY, WorkingShift.DayOfWeek.TUESDAY, WorkingShift.DayOfWeek.WEDNESDAY, WorkingShift.DayOfWeek.THURSDAY, WorkingShift.DayOfWeek.FRIDAY],
                time(8, 0),
                time(17, 0),
            ),
            "ortho": (
                [WorkingShift.DayOfWeek.MONDAY, WorkingShift.DayOfWeek.TUESDAY, WorkingShift.DayOfWeek.WEDNESDAY, WorkingShift.DayOfWeek.THURSDAY, WorkingShift.DayOfWeek.FRIDAY],
                time(9, 0),
                time(16, 0),
            ),
            "surgery": (
                [WorkingShift.DayOfWeek.SUNDAY, WorkingShift.DayOfWeek.MONDAY, WorkingShift.DayOfWeek.TUESDAY, WorkingShift.DayOfWeek.WEDNESDAY, WorkingShift.DayOfWeek.THURSDAY],
                time(10, 0),
                time(18, 0),
            ),
            "endo": (
                [WorkingShift.DayOfWeek.MONDAY, WorkingShift.DayOfWeek.WEDNESDAY, WorkingShift.DayOfWeek.FRIDAY],
                time(8, 0),
                time(14, 0),
            ),
        }
        today = WorkingShift.DayOfWeek(timezone.localdate().strftime("%A"))
        today_hours = {
            "doctor": (time(8, 0), time(17, 0)),
            "ortho": (time(9, 0), time(16, 0)),
            "surgery": (time(10, 0), time(18, 0)),
            "endo": (time(8, 0), time(14, 0)),
        }
        for key, (days, start_time, end_time) in weekday_sets.items():
            for day in set([*days, today]):
                desired_start, desired_end = today_hours[key] if day == today else (start_time, end_time)
                self.ensure_shift(profiles[key], day, desired_start, desired_end)

    def ensure_shift(self, profile, day, start_time, end_time):
        covering = WorkingShift.objects.filter(
            employee_profile=profile,
            day_of_week=day,
            is_active=True,
            start_time__lte=start_time,
            end_time__gte=end_time,
        ).first()
        if covering:
            self.count("working shifts", False)
            return covering

        overlapping = WorkingShift.objects.filter(
            employee_profile=profile,
            day_of_week=day,
            is_active=True,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).first()
        if overlapping:
            overlapping.start_time = min(overlapping.start_time, start_time)
            overlapping.end_time = max(overlapping.end_time, end_time)
            overlapping.save()
            self.count("working shifts", False)
            return overlapping

        shift, created = WorkingShift.objects.update_or_create(
            employee_profile=profile,
            day_of_week=day,
            start_time=start_time,
            defaults={"end_time": end_time, "is_active": True},
        )
        self.count("working shifts", created)
        return shift

    def demo_dates(self):
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        next_monday = monday + timedelta(days=7)
        return {
            "today": today,
            "tomorrow": today + timedelta(days=1),
            "monday": monday,
            "next_monday": next_monday,
        }

    def local_dt(self, target_date, hour, minute=0):
        settings = ClinicSettings.get_solo()
        clinic_tz = ZoneInfo(settings.clinic_timezone)
        return datetime.combine(target_date, time(hour, minute), tzinfo=clinic_tz)

    def ensure_leave_blocks(self, profiles, admin_user, dates):
        blocks = [
            ("ortho-training", profiles["ortho"], dates["tomorrow"], 11, 12, AvailabilityException.Reason.TRAINING, "Demo training block"),
            ("surgery-unavailable", profiles["surgery"], dates["today"], 14, 15, AvailabilityException.Reason.PERSONAL, "Demo unavailable block"),
            ("endo-conference", profiles["endo"], dates["next_monday"] + timedelta(days=2), 8, 12, AvailabilityException.Reason.TRAINING, "Demo conference"),
        ]
        for key, profile, day, start_hour, end_hour, reason, label in blocks:
            note = f"{DEMO_PREFIX}: {key} - {label}"
            existing = AvailabilityException.objects.filter(
                employee_profile=profile,
                note=note,
            ).order_by("id")
            block = existing.first()
            created = block is None
            if block is None:
                block = AvailabilityException(employee_profile=profile, note=note)
            if existing.count() > 1:
                existing.exclude(pk=block.pk).delete()
            block.start_at = self.local_dt(day, start_hour)
            block.end_at = self.local_dt(day, end_hour)
            block.reason = reason
            block.status = AvailabilityException.Status.ACTIVE
            block.created_by = admin_user
            block.save()
            self.count("leave/availability", created)

    def ensure_patients(self):
        histories = [
            "Patient reports sensitivity to cold. No systemic concerns noted.",
            "No known conditions.",
            "Demo-only history: previous restoration and mild gum sensitivity.",
            "Long demo medical history note for drawer layout testing. Patient reports intermittent jaw discomfort, sensitivity after sweet foods, and prefers morning appointments.",
        ]
        blood_groups = [choice.value for choice in Patient.BloodGroup]
        patients = []
        today = timezone.localdate()
        for idx in range(1, 25):
            dob = date(today.year - (18 + (idx * 3) % 55), ((idx - 1) % 12) + 1, min(28, idx))
            patient, created = Patient.objects.update_or_create(
                national_id_or_passport=f"DEMO-PAT-{idx:03d}",
                defaults={
                    "first_name": "Demo Patient",
                    "last_name": f"{idx:02d}",
                    "gender": Patient.Gender.FEMALE if idx % 2 else Patient.Gender.MALE,
                    "date_of_birth": dob,
                    "phone_number": f"+1-555-2{idx:03d}",
                    "email": f"demo.patient.{idx:02d}@example.com",
                    "address": f"{idx} Demo Clinic Street",
                    "medical_conditions_history": histories[idx % len(histories)],
                    "blood_group": blood_groups[idx % len(blood_groups)],
                    "insurance_info": "" if idx in {8, 15, 22} else f"Demo Insurance Plan {idx:02d}",
                    "emergency_contact": "" if idx in {9, 16, 23} else f"Demo Contact {idx:02d} +1-555-3{idx:03d}",
                },
            )
            patients.append(patient)
            self.count("patients", created)
        return patients

    def ensure_appointments(self, patients, profiles, staff_user, dates):
        appointments = {}
        active_conflict = Visit.objects.filter(
            doctor_profile=profiles["doctor"],
            status=Visit.Status.ACTIVE,
        ).exclude(appointment__notes=f"{DEMO_PREFIX}: today-active-treatment").exists()

        specs = []
        specs += [
            ("today-scheduled-1", 0, "doctor", dates["today"], 8, Appointment.Status.SCHEDULED, Appointment.VisitType.ROUTINE_CHECKUP),
            ("today-arrived", 1, "doctor", dates["today"], 9, Appointment.Status.ARRIVED, Appointment.VisitType.INITIAL_CONSULTATION),
            ("today-checked-in", 2, "doctor", dates["today"], 10, Appointment.Status.CHECKED_IN, Appointment.VisitType.CLEANING_VISIT),
            ("today-active-treatment", 3, "doctor", dates["today"], 11, Appointment.Status.IN_VISIT if not active_conflict else Appointment.Status.CHECKED_IN, Appointment.VisitType.TREATMENT_CONTINUATION),
            ("today-completed", 4, "doctor", dates["today"], 13, Appointment.Status.COMPLETED, Appointment.VisitType.FOLLOW_UP_VISIT),
            ("today-ortho-scheduled", 5, "ortho", dates["today"], 9, Appointment.Status.SCHEDULED, Appointment.VisitType.INITIAL_CONSULTATION),
            ("today-ortho-arrived", 6, "ortho", dates["today"], 10, Appointment.Status.ARRIVED, Appointment.VisitType.ROUTINE_CHECKUP),
            ("today-ortho-needs-reschedule", 7, "ortho", dates["today"], 12, Appointment.Status.NEEDS_RESCHEDULE, Appointment.VisitType.ROUTINE_CHECKUP),
            ("today-ortho-completed", 8, "ortho", dates["today"], 13, Appointment.Status.COMPLETED, Appointment.VisitType.X_RAY_REVIEW),
            ("today-surgery-scheduled", 9, "surgery", dates["today"], 10, Appointment.Status.SCHEDULED, Appointment.VisitType.EMERGENCY_VISIT),
            ("today-surgery-cancelled", 10, "surgery", dates["today"], 11, Appointment.Status.CANCELLED, Appointment.VisitType.ROUTINE_CHECKUP),
            ("today-surgery-no-show", 11, "surgery", dates["today"], 12, Appointment.Status.NO_SHOW, Appointment.VisitType.ROUTINE_CHECKUP),
            ("today-surgery-postponed", 12, "surgery", dates["today"], 15, Appointment.Status.POSTPONED, Appointment.VisitType.ROUTINE_CHECKUP),
            ("today-endo-scheduled", 13, "endo", dates["today"], 8, Appointment.Status.SCHEDULED, Appointment.VisitType.INITIAL_CONSULTATION),
            ("today-endo-completed", 14, "endo", dates["today"], 9, Appointment.Status.COMPLETED, Appointment.VisitType.FOLLOW_UP_VISIT),
            ("today-endo-scheduled-2", 15, "endo", dates["today"], 10, Appointment.Status.SCHEDULED, Appointment.VisitType.ROUTINE_CHECKUP),
        ]

        for idx in range(12):
            day = dates["today"] - timedelta(days=2 + idx * 2)
            profile_key = ["doctor", "ortho", "surgery", "endo"][idx % 4]
            status = Appointment.Status.COMPLETED if idx < 10 else [Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW][idx - 10]
            specs.append((f"past-{idx + 1:02d}", idx % 24, profile_key, day, [8, 9, 10, 11, 13, 15][idx % 6], status, Appointment.VisitType.ROUTINE_CHECKUP))

        future_days = [
            dates["tomorrow"],
            dates["monday"] + timedelta(days=2),
            dates["monday"] + timedelta(days=3),
            dates["next_monday"],
            dates["next_monday"] + timedelta(days=1),
            dates["next_monday"] + timedelta(days=2),
        ]
        for idx in range(16):
            profile_key = ["doctor", "ortho", "surgery", "endo"][idx % 4]
            hour_by_profile = {
                "doctor": [8, 9, 10, 13],
                "ortho": [9, 10, 13, 14],
                "surgery": [10, 11, 12, 15],
                "endo": [8, 9, 12, 13],
            }
            day = future_days[idx % len(future_days)]
            hour = hour_by_profile[profile_key][idx // 4 % 4]
            specs.append((f"future-{idx + 1:02d}", (idx + 8) % 24, profile_key, day, hour, Appointment.Status.SCHEDULED, Appointment.VisitType.FOLLOW_UP_VISIT))

        for key, patient_idx, profile_key, day, hour, status, visit_type in specs:
            note = f"{DEMO_PREFIX}: {key}"
            existing = Appointment.objects.filter(notes=note).first()
            start_at = self.find_open_appointment_start(
                profiles[profile_key],
                day,
                hour,
                status,
                existing_id=existing.id if existing else None,
            )
            appointment, created = Appointment.objects.update_or_create(
                notes=note,
                defaults={
                    "patient": patients[patient_idx],
                    "doctor_profile": profiles[profile_key],
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

    def find_open_appointment_start(self, profile, day, hour, status, existing_id=None):
        for day_offset in range(42):
            candidate_date = day + timedelta(days=day_offset)
            candidate_hours = list(range(hour, 18)) + list(range(8, hour))
            for candidate_hour in candidate_hours:
                start_at = self.local_dt(candidate_date, candidate_hour)
                end_at = start_at + timedelta(minutes=45)
                if not self.slot_is_inside_shift(profile, start_at, end_at):
                    continue
                if self.slot_overlaps_leave(profile, start_at, end_at):
                    continue
                if status in Appointment.BLOCKING_STATUSES and self.slot_overlaps_blocking_appointment(
                    profile,
                    start_at,
                    end_at,
                    existing_id,
                ):
                    continue
                if status in Appointment.BLOCKING_STATUSES and self.slot_exceeds_clinic_capacity(
                    start_at,
                    end_at,
                    existing_id,
                ):
                    continue
                return start_at
        raise CommandError(
            f"Could not find an open demo appointment slot for {profile.user.email}."
        )

    def slot_is_inside_shift(self, profile, start_at, end_at):
        settings = ClinicSettings.get_solo()
        clinic_tz = ZoneInfo(settings.clinic_timezone)
        local_start = start_at.astimezone(clinic_tz)
        local_end = end_at.astimezone(clinic_tz)
        if local_start.date() != local_end.date():
            return False
        day = WorkingShift.DayOfWeek(local_start.strftime("%A"))
        return WorkingShift.objects.filter(
            employee_profile=profile,
            day_of_week=day,
            is_active=True,
            start_time__lte=local_start.time(),
            end_time__gte=local_end.time(),
        ).exists()

    def slot_overlaps_leave(self, profile, start_at, end_at):
        return AvailabilityException.objects.filter(
            employee_profile=profile,
            status=AvailabilityException.Status.ACTIVE,
            start_at__lt=end_at,
            end_at__gt=start_at,
        ).exists()

    def slot_overlaps_blocking_appointment(self, profile, start_at, end_at, existing_id):
        queryset = Appointment.objects.filter(
            doctor_profile=profile,
            status__in=Appointment.BLOCKING_STATUSES,
            start_at__lt=end_at,
            end_at__gt=start_at,
        )
        if existing_id:
            queryset = queryset.exclude(pk=existing_id)
        return queryset.exists()

    def slot_exceeds_clinic_capacity(self, start_at, end_at, existing_id):
        settings = ClinicSettings.get_solo()
        queryset = Appointment.objects.filter(
            status__in=Appointment.BLOCKING_STATUSES,
            start_at__lt=end_at,
            end_at__gt=start_at,
        )
        if existing_id:
            queryset = queryset.exclude(pk=existing_id)
        return queryset.count() >= settings.max_simultaneous_appointments

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

    def ensure_visits(self, appointments, primary_doctor):
        visits = {}
        for key, appointment in appointments.items():
            if appointment.status == Appointment.Status.COMPLETED:
                visit, created = Visit.objects.update_or_create(
                    appointment=appointment,
                    defaults={
                        "patient": appointment.patient,
                        "doctor_profile": appointment.doctor_profile,
                        "status": Visit.Status.COMPLETED,
                        "subjective_notes": "Patient reports sensitivity to cold.",
                        "objective_notes": "Clinical exam shows demo findings for manual testing.",
                        "assessment_notes": "Demo assessment recorded for frontend review.",
                        "plan_notes": "Treatment plan discussed; follow-up recommended.",
                        "general_notes": f"{DEMO_PREFIX}: completed visit notes for {key}",
                        "started_at": appointment.start_at,
                        "completed_at": appointment.end_at,
                    },
                )
                visits[key] = visit
                self.count("visits", created)

        active_appt = appointments.get("today-active-treatment")
        if active_appt and active_appt.status == Appointment.Status.IN_VISIT:
            existing_active = Visit.objects.filter(
                doctor_profile=primary_doctor,
                status=Visit.Status.ACTIVE,
            ).exclude(appointment=active_appt).first()
            if existing_active:
                visits["active"] = existing_active
                self.count("visits", False)
            else:
                visit, created = Visit.objects.update_or_create(
                    appointment=active_appt,
                    defaults={
                        "patient": active_appt.patient,
                        "doctor_profile": active_appt.doctor_profile,
                        "status": Visit.Status.ACTIVE,
                        "subjective_notes": "Patient reports active treatment discomfort.",
                        "objective_notes": "Demo active visit exam notes.",
                        "assessment_notes": "Demo active visit assessment.",
                        "plan_notes": "Continue treatment and update notes during visit.",
                        "general_notes": f"{DEMO_PREFIX}: active visit notes",
                        "started_at": active_appt.start_at,
                        "completed_at": None,
                    },
                )
                visits["active"] = visit
                self.count("visits", created)
        return visits

    def ensure_billing(self, visits, doctor_user, staff_user):
        completed_visits = [visit for visit in visits.values() if visit.status == Visit.Status.COMPLETED]
        specs = [
            ("pending-1", "180.00", Invoice.Status.PENDING, []),
            ("pending-2", "220.00", Invoice.Status.PENDING, []),
            ("pending-3", "95.00", Invoice.Status.PENDING, []),
            ("partial-1", "240.00", Invoice.Status.PENDING, ["100.00"]),
            ("partial-2", "320.00", Invoice.Status.PENDING, ["150.00"]),
            ("partial-3", "410.00", Invoice.Status.PENDING, ["200.00"]),
            ("paid-1", "150.00", Invoice.Status.PENDING, ["150.00"]),
            ("paid-2", "275.00", Invoice.Status.PENDING, ["275.00"]),
            ("paid-3", "360.00", Invoice.Status.PENDING, ["360.00"]),
            ("cancelled-1", "90.00", Invoice.Status.CANCELLED, []),
        ]
        invoices = []
        for idx, (key, amount, status, payments) in enumerate(specs):
            visit = completed_visits[idx]
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
            Payment.objects.filter(invoice=invoice, note__startswith=DEMO_PREFIX).delete()
            self.count("invoices", created)
            for payment_amount in payments:
                self.ensure_payment(invoice, payment_amount, staff_user)
            if status == Invoice.Status.CANCELLED:
                self.ensure_invoice_cancel_log(invoice, staff_user)
            else:
                invoice.status = invoice.calculated_status
                invoice.save(update_fields=["status", "updated_at"])
            invoices.append(invoice)
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

    def ensure_attachments(self, patients, visits, staff_user):
        completed_visits = [visit for visit in visits.values() if visit.status == Visit.Status.COMPLETED]
        attachments = []
        for idx in range(1, 9):
            patient = patients[idx - 1]
            visit = completed_visits[idx - 1] if idx <= min(4, len(completed_visits)) else None
            filename = f"demo_xray_patient_{idx:02d}.png"
            attachment = Attachment.objects.filter(
                original_filename=filename,
                description__startswith=DEMO_PREFIX,
                is_deleted=False,
            ).first()
            created = attachment is None
            if attachment is None:
                attachment = Attachment(original_filename=filename)
                attachment.file.save(filename, ContentFile(PNG_BYTES), save=False)
            attachment.patient = visit.patient if visit else patient
            attachment.visit = visit
            attachment.uploaded_by = staff_user
            attachment.content_type = "image/png"
            attachment.size_bytes = len(PNG_BYTES)
            attachment.attachment_type = Attachment.AttachmentType.XRAY
            attachment.description = f"{DEMO_PREFIX}: scenario X-ray {idx:02d}"
            if not attachment.file or not attachment.file.storage.exists(attachment.file.name):
                attachment.file.save(filename, ContentFile(PNG_BYTES), save=False)
            attachment.save()
            attachments.append(attachment)
            self.count("attachments", created)
        return attachments

    def ensure_ai_results(self, attachments, doctor_user):
        finding_sets = [
            [("36", "Caries", 0.82), ("46", "Periapical Lesion", 0.64)],
            [("16", "Deep Caries", 0.91), ("26", "Caries", 0.78), ("47", "Impacted", 0.71)],
            [("36", "Deep Caries", 0.84), ("46", "Caries", 0.62)],
            [("16", "Caries", 0.71), ("26", "Periapical Lesion", 0.78), ("36", "Caries", 0.84), ("47", "Impacted", 0.62)],
        ]
        for idx, attachment in enumerate(attachments[:4], start=1):
            result, created = AIResult.objects.update_or_create(
                attachment=attachment,
                model_name="Demo Stored AI Result",
                model_version=f"demo-seed-completed-{idx}",
                defaults={
                    "patient": attachment.patient,
                    "visit": attachment.visit,
                    "status": AIResult.Status.COMPLETED,
                    "result_summary": f"Demo completed AI result {idx} for frontend review.",
                    "overall_confidence": 0.71 + (idx * 0.04),
                    "overlay_url": "",
                    "error_message": "",
                    "metadata": {"seed": "seed_demo_data", "demoOnly": True},
                    "created_by": doctor_user,
                },
            )
            self.count("AI results", created)
            for tooth, label, confidence in finding_sets[idx - 1]:
                self.ensure_ai_finding(result, tooth, label, confidence)

        self.ensure_ai_status_result(attachments[4], "processing", AIResult.Status.PROCESSING, "", None, "Demo result still processing.", doctor_user)
        self.ensure_ai_status_result(attachments[5], "failed", AIResult.Status.FAILED, "Demo AI processing failed for error-state testing.", None, "", doctor_user)

    def ensure_ai_status_result(self, attachment, key, status, error_message, confidence, summary, doctor_user):
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
                "error_message": error_message,
                "metadata": {"seed": "seed_demo_data", "demoOnly": True},
                "created_by": doctor_user,
            },
        )
        result.findings.all().delete()
        self.count("AI results", created)

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
