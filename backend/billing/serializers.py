from rest_framework import serializers

from visits.models import Visit

from .models import Invoice


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
            "status",
            "version",
            "createdAt",
            "updatedAt",
        )

    def validate_totalAmount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total amount must be positive.")
        return value
