from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsActiveUser, is_admin, is_doctor, is_staff_role

from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer


User = get_user_model()


class EmployeeProfileListCreateView(APIView):
    permission_classes = [IsActiveUser]

    def get_queryset(self):
        queryset = EmployeeProfile.objects.select_related("user")

        role = self.request.query_params.get("role", "").strip()
        if role:
            if role not in {User.Role.DOCTOR, User.Role.STAFF}:
                raise serializers.ValidationError(
                    {"role": ["Role must be Doctor or Staff."]}
                )
            queryset = queryset.filter(user__role=role)

        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search)
                | Q(user__full_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(phone__icontains=search)
                | Q(specialty__icontains=search)
            )

        return queryset

    def get(self, request):
        if not (is_admin(request.user) or is_staff_role(request.user)):
            raise PermissionDenied("Doctors can read only their own profile.")

        serializer = EmployeeProfileSerializer(self.get_queryset(), many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        if not is_admin(request.user):
            raise PermissionDenied("Only Admin can create employee profiles.")

        serializer = EmployeeProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EmployeeProfileMeView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        if not (is_staff_role(request.user) or is_doctor(request.user)):
            raise PermissionDenied("Only Staff or Doctor users can have employee profiles.")

        profile = get_object_or_404(
            EmployeeProfile.objects.select_related("user"),
            user=request.user,
        )
        return Response(EmployeeProfileSerializer(profile).data)


class EmployeeProfileDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, profile_id):
        profile = get_object_or_404(
            EmployeeProfile.objects.select_related("user"),
            pk=profile_id,
        )
        if not self._can_read_profile(request.user, profile):
            raise PermissionDenied("You do not have access to this employee profile.")

        return Response(EmployeeProfileSerializer(profile).data)

    def patch(self, request, profile_id):
        return self._update(request, profile_id, partial=True)

    def put(self, request, profile_id):
        return self._update(request, profile_id, partial=False)

    def _update(self, request, profile_id, *, partial):
        if not is_admin(request.user):
            raise PermissionDenied("Only Admin can update employee profiles.")

        request_version = self._parse_request_version(request.data)

        with transaction.atomic():
            profile = get_object_or_404(
                EmployeeProfile.objects.select_for_update().select_related("user"),
                pk=profile_id,
            )
            if profile.version != request_version:
                return Response(
                    {
                        "detail": "Version conflict",
                        "currentVersion": profile.version,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = EmployeeProfileSerializer(
                profile,
                data=request.data,
                partial=partial,
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(version=profile.version + 1)
            return Response(serializer.data)

    def _can_read_profile(self, user, profile):
        return (
            is_admin(user)
            or is_staff_role(user)
            or (is_doctor(user) and profile.user_id == user.id)
        )

    def _parse_request_version(self, data):
        if "version" not in data:
            raise serializers.ValidationError(
                {"version": ["This field is required."]}
            )

        try:
            version = int(data["version"])
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                {"version": ["A valid integer is required."]}
            ) from exc

        if version < 1:
            raise serializers.ValidationError(
                {"version": ["Version must be at least 1."]}
            )
        return version
