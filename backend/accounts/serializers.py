from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source="full_name")
    mustChangePassword = serializers.BooleanField(source="must_change_password")

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "fullName",
            "role",
            "status",
            "mustChangePassword",
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        username_or_email = attrs["username"]
        password = attrs["password"]

        username = username_or_email
        user_by_email = User.objects.filter(email__iexact=username_or_email).first()
        if user_by_email is not None:
            username = user_by_email.username

        candidate = user_by_email or User.objects.filter(username=username_or_email).first()
        if (
            candidate is not None
            and candidate.status != User.Status.ACTIVE
            and candidate.check_password(password)
        ):
            raise PermissionDenied("Inactive users cannot log in.")

        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=password,
        )
        if user is None:
            raise AuthenticationFailed("Unable to log in with the provided credentials.")
        if user.status != User.Status.ACTIVE:
            raise serializers.ValidationError(
                "Inactive users cannot log in.",
                code="inactive",
            )
        return {"user": user}
