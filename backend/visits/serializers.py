from rest_framework import serializers

from .models import Visit


class VisitSerializer(serializers.ModelSerializer):
    appointmentId = serializers.IntegerField(source="appointment_id", read_only=True)
    patientId = serializers.IntegerField(source="patient_id", read_only=True)
    patientName = serializers.CharField(source="patient.full_name", read_only=True)
    doctorProfileId = serializers.IntegerField(source="doctor_profile_id", read_only=True)
    doctorName = serializers.CharField(
        source="doctor_profile.user.full_name",
        read_only=True,
    )
    subjectiveNotes = serializers.CharField(
        source="subjective_notes",
        required=False,
        allow_blank=True,
    )
    objectiveNotes = serializers.CharField(
        source="objective_notes",
        required=False,
        allow_blank=True,
    )
    assessmentNotes = serializers.CharField(
        source="assessment_notes",
        required=False,
        allow_blank=True,
    )
    planNotes = serializers.CharField(
        source="plan_notes",
        required=False,
        allow_blank=True,
    )
    generalNotes = serializers.CharField(
        source="general_notes",
        required=False,
        allow_blank=True,
    )
    visitDate = serializers.DateTimeField(source="started_at", read_only=True)
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    completedAt = serializers.DateTimeField(source="completed_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Visit
        fields = (
            "id",
            "appointmentId",
            "patientId",
            "patientName",
            "doctorProfileId",
            "doctorName",
            "status",
            "subjectiveNotes",
            "objectiveNotes",
            "assessmentNotes",
            "planNotes",
            "generalNotes",
            "visitDate",
            "startedAt",
            "completedAt",
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
            "status",
            "visitDate",
            "startedAt",
            "completedAt",
            "version",
            "createdAt",
            "updatedAt",
        )
