from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum

from employees.models import EmployeeProfile
from patients.models import Patient
from visits.models import Visit


class Invoice(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PARTIALLY_PAID = "Partially Paid", "Partially Paid"
        PAID = "Paid", "Paid"
        CANCELLED = "Cancelled", "Cancelled"

    visit = models.OneToOneField(
        Visit,
        on_delete=models.PROTECT,
        related_name="invoice",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    doctor_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_invoices",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["doctor_profile", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def clean(self):
        errors = {}

        if self.total_amount is not None and self.total_amount <= Decimal("0"):
            errors["total_amount"] = "Total amount must be positive."

        if self.doctor_profile_id:
            User = get_user_model()
            doctor_user = getattr(self.doctor_profile, "user", None)
            if getattr(doctor_user, "role", None) != User.Role.DOCTOR:
                errors["doctor_profile"] = "Invoice doctor profile must belong to a Doctor."

        if self.visit_id:
            if self.patient_id and self.visit.patient_id != self.patient_id:
                errors["patient"] = "Invoice patient must match the visit patient."
            if (
                self.doctor_profile_id
                and self.visit.doctor_profile_id != self.doctor_profile_id
            ):
                errors["doctor_profile"] = (
                    "Invoice doctor profile must match the visit doctor."
                )

        if errors:
            raise ValidationError(errors)

    @property
    def paid_amount(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("payments")
        if prefetched is not None:
            return sum((payment.amount for payment in prefetched), Decimal("0.00"))

        total = self.payments.aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0.00")

    @property
    def balance(self):
        return max(self.total_amount - self.paid_amount, Decimal("0.00"))

    @property
    def calculated_status(self):
        if self.status == self.Status.CANCELLED:
            return self.Status.CANCELLED

        paid_amount = self.paid_amount
        if paid_amount <= Decimal("0.00"):
            return self.Status.PENDING
        if paid_amount < self.total_amount:
            return self.Status.PARTIALLY_PAID
        return self.Status.PAID

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Invoice {self.pk} for {self.patient}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "Cash", "Cash"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CASH,
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_payments",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["invoice", "created_at"]),
            models.Index(fields=["received_by", "created_at"]),
        ]

    def clean(self):
        errors = {}

        if self.amount is not None and self.amount <= Decimal("0.00"):
            errors["amount"] = "Payment amount must be positive."

        if self.method != self.Method.CASH:
            errors["method"] = "Phase 11 supports Cash payments only."

        if self.invoice_id:
            if self.invoice.status == Invoice.Status.CANCELLED:
                errors["invoice"] = "Payments cannot be added to Cancelled invoices."

            paid_excluding_self = Payment.objects.filter(
                invoice_id=self.invoice_id,
            )
            if self.pk:
                paid_excluding_self = paid_excluding_self.exclude(pk=self.pk)
            total_paid = (
                paid_excluding_self.aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )
            balance = self.invoice.total_amount - total_paid
            if self.amount is not None and self.amount > balance:
                errors["amount"] = "Payment amount cannot exceed invoice balance."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Payment {self.pk} for invoice {self.invoice_id}"


class InvoiceAuditLog(models.Model):
    class Action(models.TextChoices):
        TOTAL_EDIT = "Total Edit", "Total Edit"
        CANCEL = "Cancel", "Cancel"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    previous_total = models.DecimalField(max_digits=10, decimal_places=2)
    new_total = models.DecimalField(max_digits=10, decimal_places=2)
    previous_status = models.CharField(max_length=20, choices=Invoice.Status.choices)
    new_status = models.CharField(max_length=20, choices=Invoice.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoice_audit_logs",
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(fields=["invoice", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and InvoiceAuditLog.objects.filter(pk=self.pk).exists():
            raise ValidationError("Invoice audit logs are append-only.")
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.action} for invoice {self.invoice_id}"
