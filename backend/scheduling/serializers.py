from rest_framework import serializers

from employees.models import EmployeeProfile
from patients.models import Patient

from .models import Appointment, AppointmentChangeLog, AvailabilityException, WorkingShift


class WorkingShiftSerializer(serializers.ModelSerializer):
    employeeProfileId = serializers.PrimaryKeyRelatedField(
        source="employee_profile",
        queryset=EmployeeProfile.objects.select_related("user").all(),
    )
    userId = serializers.IntegerField(source="employee_profile.user_id", read_only=True)
    fullName = serializers.CharField(
        source="employee_profile.user.full_name",
        read_only=True,
    )
    role = serializers.CharField(source="employee_profile.user.role", read_only=True)
    specialty = serializers.CharField(source="employee_profile.specialty", read_only=True)
    dayOfWeek = serializers.ChoiceField(
        source="day_of_week",
        choices=WorkingShift.DayOfWeek.choices,
    )
    startTime = serializers.TimeField(source="start_time", format="%H:%M")
    endTime = serializers.TimeField(source="end_time", format="%H:%M")
    isActive = serializers.BooleanField(source="is_active", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WorkingShift
        fields = (
            "id",
            "employeeProfileId",
            "userId",
            "fullName",
            "role",
            "specialty",
            "dayOfWeek",
            "startTime",
            "endTime",
            "isActive",
            "version",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "userId",
            "fullName",
            "role",
            "specialty",
            "version",
            "createdAt",
            "updatedAt",
        )


class AvailabilityExceptionSerializer(serializers.ModelSerializer):
    employeeProfileId = serializers.PrimaryKeyRelatedField(
        source="employee_profile",
        queryset=EmployeeProfile.objects.select_related("user").all(),
    )
    userId = serializers.IntegerField(source="employee_profile.user_id", read_only=True)
    fullName = serializers.CharField(
        source="employee_profile.user.full_name",
        read_only=True,
    )
    role = serializers.CharField(source="employee_profile.user.role", read_only=True)
    specialty = serializers.CharField(source="employee_profile.specialty", read_only=True)
    startAt = serializers.DateTimeField(source="start_at")
    endAt = serializers.DateTimeField(source="end_at")
    createdBy = serializers.IntegerField(source="created_by_id", read_only=True)
    cancelledAt = serializers.DateTimeField(source="cancelled_at", read_only=True)
    cancelledBy = serializers.IntegerField(source="cancelled_by_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = AvailabilityException
        fields = (
            "id",
            "employeeProfileId",
            "userId",
            "fullName",
            "role",
            "specialty",
            "startAt",
            "endAt",
            "reason",
            "note",
            "status",
            "version",
            "createdBy",
            "cancelledAt",
            "cancelledBy",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "userId",
            "fullName",
            "role",
            "specialty",
            "version",
            "createdBy",
            "cancelledAt",
            "cancelledBy",
            "createdAt",
            "updatedAt",
        )


class AppointmentSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(
        source="patient",
        queryset=Patient.objects.all(),
    )
    patientName = serializers.CharField(source="patient.full_name", read_only=True)
    doctorProfileId = serializers.PrimaryKeyRelatedField(
        source="doctor_profile",
        queryset=EmployeeProfile.objects.select_related("user").all(),
    )
    doctorName = serializers.CharField(
        source="doctor_profile.user.full_name",
        read_only=True,
    )
    startAt = serializers.DateTimeField(source="start_at")
    endAt = serializers.DateTimeField(source="end_at")
    durationMinutes = serializers.IntegerField(
        source="duration_minutes",
        min_value=Appointment.MIN_DURATION_MINUTES,
    )
    visitType = serializers.ChoiceField(
        source="visit_type",
        choices=Appointment.VisitType.choices,
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Appointment
        fields = (
            "id",
            "patientId",
            "patientName",
            "doctorProfileId",
            "doctorName",
            "startAt",
            "endAt",
            "durationMinutes",
            "visitType",
            "status",
            "notes",
            "version",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "patientName",
            "doctorName",
            "status",
            "version",
            "createdAt",
            "updatedAt",
        )

    def to_internal_value(self, data):
        incoming = data.copy()
        if "doctorProfileId" not in incoming and "doctorId" in incoming:
            incoming["doctorProfileId"] = incoming["doctorId"]
        return super().to_internal_value(incoming)


class AppointmentChangeLogSerializer(serializers.ModelSerializer):
    logId = serializers.IntegerField(source="id", read_only=True)
    appointmentId = serializers.IntegerField(source="appointment_id", read_only=True)
    oldDoctorId = serializers.IntegerField(
        source="old_doctor_profile_id",
        read_only=True,
    )
    newDoctorId = serializers.IntegerField(
        source="new_doctor_profile_id",
        read_only=True,
    )
    oldStartAt = serializers.DateTimeField(source="old_start_at", read_only=True)
    oldEndAt = serializers.DateTimeField(source="old_end_at", read_only=True)
    newStartAt = serializers.DateTimeField(source="new_start_at", read_only=True)
    newEndAt = serializers.DateTimeField(source="new_end_at", read_only=True)
    oldStatus = serializers.CharField(source="previous_status", read_only=True)
    newStatus = serializers.CharField(source="new_status", read_only=True)
    changedBy = serializers.IntegerField(source="changed_by_id", read_only=True)
    changedAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AppointmentChangeLog
        fields = (
            "logId",
            "appointmentId",
            "action",
            "oldDoctorId",
            "newDoctorId",
            "oldStartAt",
            "oldEndAt",
            "newStartAt",
            "newEndAt",
            "oldStatus",
            "newStatus",
            "reason",
            "note",
            "changedBy",
            "changedAt",
            "metadata",
        )
        read_only_fields = fields
