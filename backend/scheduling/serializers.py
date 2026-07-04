from rest_framework import serializers

from employees.models import EmployeeProfile

from .models import WorkingShift


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
