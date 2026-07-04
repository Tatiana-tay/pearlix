from rest_framework import serializers

from employees.models import EmployeeProfile

from .models import AvailabilityException, WorkingShift


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
