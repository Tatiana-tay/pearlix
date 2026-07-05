from django.utils import timezone
from rest_framework import serializers

from .models import Patient


class PatientSerializer(serializers.ModelSerializer):
    patientId = serializers.IntegerField(source="id", read_only=True)
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    fullName = serializers.CharField(source="full_name", read_only=True)
    dateOfBirth = serializers.DateField(
        source="date_of_birth",
        allow_null=True,
        required=False,
    )
    age = serializers.IntegerField(read_only=True)
    nationalIdOrPassport = serializers.CharField(source="national_id_or_passport")
    phoneNumber = serializers.CharField(
        source="phone_number",
        allow_blank=True,
        required=False,
    )
    medicalConditionsHistory = serializers.CharField(
        source="medical_conditions_history",
        allow_blank=True,
        required=False,
    )
    bloodGroup = serializers.ChoiceField(
        source="blood_group",
        choices=Patient.BloodGroup.choices,
        allow_blank=True,
        required=False,
    )
    insuranceInfo = serializers.CharField(
        source="insurance_info",
        allow_blank=True,
        required=False,
    )
    emergencyContact = serializers.CharField(
        source="emergency_contact",
        allow_blank=True,
        required=False,
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Patient
        fields = (
            "id",
            "patientId",
            "firstName",
            "lastName",
            "fullName",
            "gender",
            "dateOfBirth",
            "age",
            "phoneNumber",
            "email",
            "nationalIdOrPassport",
            "medicalConditionsHistory",
            "bloodGroup",
            "insuranceInfo",
            "emergencyContact",
            "address",
            "version",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "patientId",
            "fullName",
            "age",
            "version",
            "createdAt",
            "updatedAt",
        )

    def validate_dateOfBirth(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value
