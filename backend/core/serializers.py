from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from .models import ClinicSettings


class ClinicSettingsSerializer(serializers.ModelSerializer):
    clinicTimezone = serializers.CharField(
        source="clinic_timezone",
        required=False,
    )
    maxSimultaneousAppointments = serializers.IntegerField(
        source="max_simultaneous_appointments",
        min_value=1,
        required=False,
    )
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = ClinicSettings
        fields = (
            "clinicTimezone",
            "maxSimultaneousAppointments",
            "updatedAt",
        )

    def validate_clinicTimezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError("Enter a valid IANA timezone name.") from exc
        return value
