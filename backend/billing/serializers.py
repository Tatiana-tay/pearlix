from rest_framework import serializers

from visits.models import Visit

from .models import Invoice, Payment


class InvoiceSerializer(serializers.ModelSerializer):
    visitId = serializers.PrimaryKeyRelatedField(
        source="visit",
        queryset=Visit.objects.select_related(
            "appointment",
            "patient",
            "doctor_profile__user",
        ).all(),
    )
    appointmentId = serializers.IntegerField(
        source="visit.appointment_id",
        read_only=True,
    )
    patientId = serializers.IntegerField(source="patient_id", read_only=True)
    patientName = serializers.CharField(source="patient.full_name", read_only=True)
    doctorProfileId = serializers.IntegerField(source="doctor_profile_id", read_only=True)
    doctorName = serializers.CharField(
        source="doctor_profile.user.full_name",
        read_only=True,
    )
    createdById = serializers.IntegerField(source="created_by_id", read_only=True)
    totalAmount = serializers.DecimalField(
        source="total_amount",
        max_digits=10,
        decimal_places=2,
    )
    paidAmount = serializers.DecimalField(
        source="paid_amount",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    balance = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
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
            "status",
            "note",
            "version",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "appointmentId",
            "patientId",
            "patientName",
            "doctorProfileId",
            "doctorName",
            "createdById",
            "paidAmount",
            "balance",
            "status",
            "version",
            "createdAt",
            "updatedAt",
        )

    def validate_totalAmount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total amount must be positive.")
        return value


class InvoiceTotalEditSerializer(serializers.Serializer):
    totalAmount = serializers.DecimalField(
        source="total_amount",
        max_digits=10,
        decimal_places=2,
    )
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)

    def validate_totalAmount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total amount must be positive.")
        return value


class InvoiceCancelSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)


class PaymentSerializer(serializers.ModelSerializer):
    invoiceId = serializers.PrimaryKeyRelatedField(
        source="invoice",
        queryset=Invoice.objects.select_related(
            "patient",
            "doctor_profile__user",
            "visit__appointment",
        ).all(),
    )
    receivedById = serializers.IntegerField(source="received_by_id", read_only=True)
    receivedByName = serializers.CharField(
        source="received_by.full_name",
        read_only=True,
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "invoiceId",
            "amount",
            "method",
            "receivedById",
            "receivedByName",
            "note",
            "createdAt",
        )
        read_only_fields = (
            "id",
            "receivedById",
            "receivedByName",
            "createdAt",
        )
        extra_kwargs = {
            "method": {"required": False},
            "note": {"required": False, "allow_blank": True},
        }

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive.")
        return value

    def validate_method(self, value):
        if value != Payment.Method.CASH:
            raise serializers.ValidationError("Phase 11 supports Cash payments only.")
        return value
