from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsActiveUser, is_admin, is_doctor, is_staff_role

from .models import WorkingShift
from .serializers import WorkingShiftSerializer


User = get_user_model()


class WorkingShiftListCreateView(APIView):
    permission_classes = [IsActiveUser]

    def get_queryset(self):
        queryset = WorkingShift.objects.select_related("employee_profile__user")

        if is_doctor(self.request.user):
            queryset = queryset.filter(employee_profile__user=self.request.user)

        employee_profile_id = self.request.query_params.get("employeeProfileId", "").strip()
        if employee_profile_id:
            try:
                employee_profile_id = int(employee_profile_id)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"employeeProfileId": ["A valid integer is required."]}
                ) from exc
            queryset = queryset.filter(employee_profile_id=employee_profile_id)

        role = self.request.query_params.get("role", "").strip()
        if role:
            if role not in {User.Role.DOCTOR, User.Role.STAFF}:
                raise serializers.ValidationError(
                    {"role": ["Role must be Doctor or Staff."]}
                )
            queryset = queryset.filter(employee_profile__user__role=role)

        day_of_week = self.request.query_params.get("dayOfWeek", "").strip()
        if day_of_week:
            valid_days = {choice.value for choice in WorkingShift.DayOfWeek}
            if day_of_week not in valid_days:
                raise serializers.ValidationError(
                    {"dayOfWeek": ["Enter a valid day of week."]}
                )
            queryset = queryset.filter(day_of_week=day_of_week)

        is_active = self.request.query_params.get("isActive", "").strip()
        if is_active:
            parsed = self._parse_bool(is_active)
            queryset = queryset.filter(is_active=parsed)

        return queryset

    def get(self, request):
        if not (is_admin(request.user) or is_staff_role(request.user) or is_doctor(request.user)):
            raise PermissionDenied("You do not have access to working shifts.")

        serializer = WorkingShiftSerializer(self.get_queryset(), many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        if not is_admin(request.user):
            raise PermissionDenied("Only Admin can create working shifts.")

        serializer = WorkingShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _parse_bool(self, value):
        normalized = value.lower()
        if normalized in {"1", "true", "yes"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False
        raise serializers.ValidationError(
            {"isActive": ["Enter true or false."]}
        )


class WorkingShiftDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, shift_id):
        shift = get_object_or_404(
            WorkingShift.objects.select_related("employee_profile__user"),
            pk=shift_id,
        )
        if not self._can_read_shift(request.user, shift):
            raise PermissionDenied("You do not have access to this working shift.")

        return Response(WorkingShiftSerializer(shift).data)

    def patch(self, request, shift_id):
        return self._update(request, shift_id, partial=True)

    def put(self, request, shift_id):
        return self._update(request, shift_id, partial=False)

    def _update(self, request, shift_id, *, partial):
        if not is_admin(request.user):
            raise PermissionDenied("Only Admin can update working shifts.")

        request_version = self._parse_request_version(request.data)

        with transaction.atomic():
            shift = get_object_or_404(
                WorkingShift.objects.select_for_update().select_related(
                    "employee_profile__user"
                ),
                pk=shift_id,
            )
            if shift.version != request_version:
                return Response(
                    {
                        "detail": "Version conflict",
                        "currentVersion": shift.version,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = WorkingShiftSerializer(
                shift,
                data=request.data,
                partial=partial,
            )
            serializer.is_valid(raise_exception=True)
            try:
                serializer.save(version=shift.version + 1)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            return Response(serializer.data)

    def _can_read_shift(self, user, shift):
        return (
            is_admin(user)
            or is_staff_role(user)
            or (is_doctor(user) and shift.employee_profile.user_id == user.id)
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
