from datetime import timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsActiveUser, is_admin, is_doctor, is_staff_role

from .models import AvailabilityException, WorkingShift
from .serializers import AvailabilityExceptionSerializer, WorkingShiftSerializer


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


class AvailabilityExceptionListCreateView(APIView):
    permission_classes = [IsActiveUser]

    def get_queryset(self):
        queryset = AvailabilityException.objects.select_related(
            "employee_profile__user",
            "created_by",
            "cancelled_by",
        )

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

        exception_status = self.request.query_params.get("status", "").strip()
        if exception_status:
            valid_statuses = {choice.value for choice in AvailabilityException.Status}
            if exception_status not in valid_statuses:
                raise serializers.ValidationError(
                    {"status": ["Enter a valid availability exception status."]}
                )
            queryset = queryset.filter(status=exception_status)

        window_start = self._parse_datetime_filter("from")
        window_end = self._parse_datetime_filter("to")
        if window_start and window_end and window_start >= window_end:
            raise serializers.ValidationError(
                {"from": ["From datetime must be before to datetime."]}
            )
        if window_start:
            queryset = queryset.filter(end_at__gt=window_start)
        if window_end:
            queryset = queryset.filter(start_at__lt=window_end)

        return queryset

    def get(self, request):
        if not (is_admin(request.user) or is_staff_role(request.user) or is_doctor(request.user)):
            raise PermissionDenied("You do not have access to availability exceptions.")

        serializer = AvailabilityExceptionSerializer(self.get_queryset(), many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        if not is_admin(request.user):
            raise PermissionDenied("Only Admin can create availability exceptions.")

        serializer = AvailabilityExceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        save_kwargs = {"created_by": request.user}
        if serializer.validated_data.get("status") == AvailabilityException.Status.CANCELLED:
            save_kwargs.update(
                {
                    "cancelled_at": timezone.now(),
                    "cancelled_by": request.user,
                }
            )

        try:
            serializer.save(**save_kwargs)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _parse_datetime_filter(self, name):
        value = self.request.query_params.get(name, "").strip()
        if not value:
            return None

        parsed = parse_datetime(value)
        if parsed is None:
            raise serializers.ValidationError(
                {name: ["Enter a valid ISO 8601 datetime."]}
            )
        if timezone.is_naive(parsed):
            raise serializers.ValidationError(
                {name: ["Datetime must include a timezone."]}
            )
        return parsed.astimezone(datetime_timezone.utc)


class AvailabilityExceptionDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, exception_id):
        exception = get_object_or_404(
            AvailabilityException.objects.select_related(
                "employee_profile__user",
                "created_by",
                "cancelled_by",
            ),
            pk=exception_id,
        )
        if not self._can_read_exception(request.user, exception):
            raise PermissionDenied("You do not have access to this availability exception.")

        return Response(AvailabilityExceptionSerializer(exception).data)

    def patch(self, request, exception_id):
        return self._update(request, exception_id, partial=True)

    def put(self, request, exception_id):
        return self._update(request, exception_id, partial=False)

    def _update(self, request, exception_id, *, partial):
        if not is_admin(request.user):
            raise PermissionDenied("Only Admin can update availability exceptions.")

        request_version = self._parse_request_version(request.data)

        with transaction.atomic():
            exception = get_object_or_404(
                AvailabilityException.objects.select_for_update().select_related(
                    "employee_profile__user",
                ),
                pk=exception_id,
            )
            if exception.version != request_version:
                return Response(
                    {
                        "detail": "Version conflict",
                        "currentVersion": exception.version,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = AvailabilityExceptionSerializer(
                exception,
                data=request.data,
                partial=partial,
            )
            serializer.is_valid(raise_exception=True)

            new_status = serializer.validated_data.get("status", exception.status)
            save_kwargs = {"version": exception.version + 1}
            if (
                new_status == AvailabilityException.Status.CANCELLED
                and exception.status != AvailabilityException.Status.CANCELLED
            ):
                save_kwargs.update(
                    {
                        "cancelled_at": timezone.now(),
                        "cancelled_by": request.user,
                    }
                )
            elif new_status == AvailabilityException.Status.ACTIVE:
                save_kwargs.update(
                    {
                        "cancelled_at": None,
                        "cancelled_by": None,
                    }
                )

            try:
                serializer.save(**save_kwargs)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            return Response(serializer.data)

    def _can_read_exception(self, user, exception):
        return (
            is_admin(user)
            or is_staff_role(user)
            or (is_doctor(user) and exception.employee_profile.user_id == user.id)
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
