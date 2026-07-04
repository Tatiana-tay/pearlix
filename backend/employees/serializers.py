from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import EmployeeProfile


User = get_user_model()


class EmployeeProfileSerializer(serializers.ModelSerializer):
    userId = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.all(),
    )
    username = serializers.CharField(source="user.username", read_only=True)
    fullName = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    status = serializers.CharField(source="user.status", read_only=True)
    avatarUrl = serializers.URLField(
        source="avatar_url",
        allow_blank=True,
        required=False,
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = (
            "id",
            "userId",
            "username",
            "fullName",
            "email",
            "role",
            "status",
            "specialty",
            "gender",
            "phone",
            "avatarUrl",
            "version",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "username",
            "fullName",
            "email",
            "role",
            "status",
            "version",
            "createdAt",
            "updatedAt",
        )

    def validate(self, attrs):
        user = attrs.get("user") or getattr(self.instance, "user", None)
        if user is None:
            raise serializers.ValidationError({"userId": ["This field is required."]})

        if self.instance is not None and attrs.get("user") is not None:
            if attrs["user"] != self.instance.user:
                raise serializers.ValidationError(
                    {"userId": ["Employee profile user cannot be changed."]}
                )

        if user.role not in {User.Role.DOCTOR, User.Role.STAFF}:
            raise serializers.ValidationError(
                {"userId": ["Employee profile user must have Doctor or Staff role."]}
            )

        if self.instance is None and EmployeeProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                {"userId": ["Employee profile already exists for this user."]}
            )

        specialty = attrs.get("specialty")
        if specialty is None and self.instance is not None:
            specialty = self.instance.specialty
        specialty = (specialty or "").strip()

        if user.role == User.Role.DOCTOR and not specialty:
            raise serializers.ValidationError(
                {"specialty": ["Doctor profiles require a specialty."]}
            )

        if user.role == User.Role.STAFF and specialty:
            raise serializers.ValidationError(
                {"specialty": ["Staff profiles cannot have a specialty."]}
            )

        if "specialty" in attrs:
            attrs["specialty"] = specialty
        return attrs
