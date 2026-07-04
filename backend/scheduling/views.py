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

from .models import Appointment, AppointmentChangeLog, AvailabilityException, WorkingShift
from .serializers import (
    AppointmentChangeLogSerializer,
    AppointmentSerializer,
    AvailabilityExceptionSerializer,
    WorkingShiftSerializer,
)


User = get_user_model()


def create_appointment_change_log(
    *,
    appointment,
    action,
    previous_status,
    new_status,
    changed_by,
    reason="",
    note="",
    old_doctor_profile=None,
    new_doctor_profile=None,
    old_start_at=None,
    old_end_at=None,
    new_start_at=None,
    new_end_at=None,
    metadata=None,
):
    return AppointmentChangeLog.objects.create(
        appointment=appointment,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        old_doctor_profile=old_doctor_profile,
        new_doctor_profile=new_doctor_profile,
        old_start_at=old_start_at,
        old_end_at=old_end_at,
        new_start_at=new_start_at,
        new_end_at=new_end_at,
        changed_by=changed_by,
        reason=reason or "",
        note=note or "",
        metadata=metadata or {},
    )


def reject_in_visit_leave_overlap(employee_profile, start_at, end_at):
    if Appointment.objects.filter(
        doctor_profile=employee_profile,
        status=Appointment.Status.IN_VISIT,
        start_at__lt=end_at,
        end_at__gt=start_at,
    ).exists():
        raise serializers.ValidationError(
            {"startAt": ["Active leave cannot overlap an In Visit appointment."]}
        )


def mark_leave_affected_appointments(availability_exception, *, changed_by=None):
    if availability_exception.status != AvailabilityException.Status.ACTIVE:
        return 0

    affected = list(
        Appointment.objects.select_for_update().filter(
            doctor_profile=availability_exception.employee_profile,
            status__in=Appointment.LEAVE_AFFECTED_STATUSES,
            start_at__lt=availability_exception.end_at,
            end_at__gt=availability_exception.start_at,
        )
    )
    now = timezone.now()
    for appointment in affected:
        previous_status = appointment.status
        Appointment.objects.filter(pk=appointment.pk).update(
            status=Appointment.Status.NEEDS_RESCHEDULE,
            version=appointment.version + 1,
            updated_at=now,
        )
        appointment.status = Appointment.Status.NEEDS_RESCHEDULE
        appointment.version += 1
        appointment.updated_at = now
        create_appointment_change_log(
            appointment=appointment,
            action=AppointmentChangeLog.Action.MARK_NEEDS_RESCHEDULE,
            previous_status=previous_status,
            new_status=Appointment.Status.NEEDS_RESCHEDULE,
            changed_by=changed_by,
            reason=f"Availability exception: {availability_exception.reason}",
            metadata={"availabilityExceptionId": availability_exception.id},
        )
    return len(affected)


def parse_request_version(data):
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


def version_conflict_response(current_version):
    return Response(
        {
            "detail": "Version conflict",
            "currentVersion": current_version,
        },
        status=status.HTTP_409_CONFLICT,
    )


def get_workflow_reason(data):
    value = data.get("reason") or data.get("note") or ""
    return str(value).strip()


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
        new_status = serializer.validated_data.get(
            "status",
            AvailabilityException.Status.ACTIVE,
        )
        if new_status == AvailabilityException.Status.CANCELLED:
            save_kwargs.update(
                {
                    "cancelled_at": timezone.now(),
                    "cancelled_by": request.user,
                }
            )

        with transaction.atomic():
            if new_status == AvailabilityException.Status.ACTIVE:
                reject_in_visit_leave_overlap(
                    serializer.validated_data["employee_profile"],
                    serializer.validated_data["start_at"],
                    serializer.validated_data["end_at"],
                )
            try:
                exception = serializer.save(**save_kwargs)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            mark_leave_affected_appointments(exception, changed_by=request.user)
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
            new_employee_profile = serializer.validated_data.get(
                "employee_profile",
                exception.employee_profile,
            )
            new_start_at = serializer.validated_data.get("start_at", exception.start_at)
            new_end_at = serializer.validated_data.get("end_at", exception.end_at)
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

            if new_status == AvailabilityException.Status.ACTIVE:
                reject_in_visit_leave_overlap(
                    new_employee_profile,
                    new_start_at,
                    new_end_at,
                )

            try:
                exception = serializer.save(**save_kwargs)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            mark_leave_affected_appointments(exception, changed_by=request.user)
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


class AppointmentListCreateView(APIView):
    permission_classes = [IsActiveUser]

    def get_queryset(self):
        queryset = Appointment.objects.select_related(
            "patient",
            "doctor_profile__user",
        )

        if is_doctor(self.request.user):
            queryset = queryset.filter(doctor_profile__user=self.request.user)

        patient_id = self.request.query_params.get("patientId", "").strip()
        if patient_id:
            try:
                patient_id = int(patient_id)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"patientId": ["A valid integer is required."]}
                ) from exc
            queryset = queryset.filter(patient_id=patient_id)

        doctor_profile_id = (
            self.request.query_params.get("doctorProfileId", "").strip()
            or self.request.query_params.get("doctorId", "").strip()
        )
        if doctor_profile_id:
            try:
                doctor_profile_id = int(doctor_profile_id)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"doctorProfileId": ["A valid integer is required."]}
                ) from exc
            queryset = queryset.filter(doctor_profile_id=doctor_profile_id)

        appointment_status = self.request.query_params.get("status", "").strip()
        if appointment_status:
            valid_statuses = {choice.value for choice in Appointment.Status}
            if appointment_status not in valid_statuses:
                raise serializers.ValidationError(
                    {"status": ["Enter a valid appointment status."]}
                )
            queryset = queryset.filter(status=appointment_status)

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
            raise PermissionDenied("You do not have access to appointments.")

        serializer = AppointmentSerializer(self.get_queryset(), many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can create appointments.")
        self._reject_status_field(request.data)

        serializer = AppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(created_by=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _reject_status_field(self, data):
        if "status" in data:
            raise serializers.ValidationError(
                {"status": ["Appointment status cannot be set in Phase 7."]}
            )

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


class AppointmentRescheduleQueueView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        if not (is_admin(request.user) or is_staff_role(request.user)):
            raise PermissionDenied("You do not have access to the reschedule queue.")

        appointments = Appointment.objects.select_related(
            "patient",
            "doctor_profile__user",
        ).filter(status=Appointment.Status.NEEDS_RESCHEDULE)
        return Response({"results": AppointmentSerializer(appointments, many=True).data})


class AppointmentDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, appointment_id):
        appointment = get_object_or_404(
            Appointment.objects.select_related("patient", "doctor_profile__user"),
            pk=appointment_id,
        )
        if not self._can_read_appointment(request.user, appointment):
            raise PermissionDenied("You do not have access to this appointment.")

        return Response(AppointmentSerializer(appointment).data)

    def patch(self, request, appointment_id):
        return self._update(request, appointment_id, partial=True)

    def put(self, request, appointment_id):
        return self._update(request, appointment_id, partial=False)

    def _update(self, request, appointment_id, *, partial):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can update appointments.")

        request_version = self._parse_request_version(request.data)
        if "status" in request.data:
            raise serializers.ValidationError(
                {"status": ["Appointment status cannot be changed in Phase 7."]}
            )

        with transaction.atomic():
            appointment = get_object_or_404(
                Appointment.objects.select_for_update().select_related(
                    "patient",
                    "doctor_profile__user",
                ),
                pk=appointment_id,
            )
            if appointment.version != request_version:
                return Response(
                    {
                        "detail": "Version conflict",
                        "currentVersion": appointment.version,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = AppointmentSerializer(
                appointment,
                data=request.data,
                partial=partial,
            )
            serializer.is_valid(raise_exception=True)
            try:
                serializer.save(version=appointment.version + 1)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            return Response(serializer.data)

    def _can_read_appointment(self, user, appointment):
        return (
            is_admin(user)
            or is_staff_role(user)
            or (is_doctor(user) and appointment.doctor_profile.user_id == user.id)
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


class AppointmentChangeLogListView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, appointment_id):
        appointment = get_object_or_404(
            Appointment.objects.select_related("doctor_profile__user"),
            pk=appointment_id,
        )
        if not self._can_read_logs(request.user, appointment):
            raise PermissionDenied("You do not have access to these appointment logs.")

        logs = appointment.change_logs.select_related(
            "changed_by",
            "old_doctor_profile",
            "new_doctor_profile",
        )
        return Response({"results": AppointmentChangeLogSerializer(logs, many=True).data})

    def _can_read_logs(self, user, appointment):
        return (
            is_admin(user)
            or is_staff_role(user)
            or (is_doctor(user) and appointment.doctor_profile.user_id == user.id)
        )


class AppointmentWorkflowActionView(APIView):
    permission_classes = [IsActiveUser]
    action = None

    TRANSITIONS = {
        "arrive": {
            "from": (Appointment.Status.SCHEDULED,),
            "to": Appointment.Status.ARRIVED,
            "log_action": AppointmentChangeLog.Action.ARRIVE,
        },
        "check-in": {
            "from": (Appointment.Status.ARRIVED,),
            "to": Appointment.Status.CHECKED_IN,
            "log_action": AppointmentChangeLog.Action.CHECK_IN,
        },
        "cancel": {
            "from": (
                Appointment.Status.SCHEDULED,
                Appointment.Status.ARRIVED,
                Appointment.Status.CHECKED_IN,
            ),
            "to": Appointment.Status.CANCELLED,
            "log_action": AppointmentChangeLog.Action.CANCEL,
        },
        "no-show": {
            "from": (
                Appointment.Status.SCHEDULED,
                Appointment.Status.ARRIVED,
                Appointment.Status.CHECKED_IN,
            ),
            "to": Appointment.Status.NO_SHOW,
            "log_action": AppointmentChangeLog.Action.MARK_NO_SHOW,
        },
        "postpone": {
            "from": (
                Appointment.Status.SCHEDULED,
                Appointment.Status.ARRIVED,
                Appointment.Status.CHECKED_IN,
            ),
            "to": Appointment.Status.POSTPONED,
            "log_action": AppointmentChangeLog.Action.POSTPONE,
        },
        "mark-needs-reschedule": {
            "from": (
                Appointment.Status.SCHEDULED,
                Appointment.Status.ARRIVED,
                Appointment.Status.CHECKED_IN,
            ),
            "to": Appointment.Status.NEEDS_RESCHEDULE,
            "log_action": AppointmentChangeLog.Action.MARK_NEEDS_RESCHEDULE,
        },
    }

    def post(self, request, appointment_id):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can perform appointment workflow actions.")

        transition = self.TRANSITIONS.get(self.action)
        if transition is None:
            raise serializers.ValidationError(
                {"action": ["Unsupported appointment workflow action."]}
            )

        request_version = parse_request_version(request.data)
        reason = get_workflow_reason(request.data)

        with transaction.atomic():
            appointment = get_object_or_404(
                Appointment.objects.select_for_update().select_related(
                    "patient",
                    "doctor_profile__user",
                ),
                pk=appointment_id,
            )
            if appointment.version != request_version:
                return version_conflict_response(appointment.version)

            if appointment.status in Appointment.TERMINAL_STATUSES:
                raise serializers.ValidationError(
                    {"status": ["Terminal appointments cannot be changed."]}
                )
            if appointment.status not in transition["from"]:
                raise serializers.ValidationError(
                    {"status": ["This status transition is not allowed."]}
                )

            previous_status = appointment.status
            new_status = transition["to"]
            Appointment.objects.filter(pk=appointment.pk).update(
                status=new_status,
                version=appointment.version + 1,
                updated_at=timezone.now(),
            )
            appointment.status = new_status
            appointment.version += 1
            appointment.refresh_from_db()
            create_appointment_change_log(
                appointment=appointment,
                action=transition["log_action"],
                previous_status=previous_status,
                new_status=new_status,
                changed_by=request.user,
                reason=reason,
            )
            return Response(AppointmentSerializer(appointment).data)


class AppointmentRescheduleView(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, appointment_id):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can reschedule appointments.")

        request_version = parse_request_version(request.data)
        reason = get_workflow_reason(request.data)
        missing_fields = [
            field
            for field in ("startAt", "endAt", "durationMinutes")
            if field not in request.data
        ]
        if missing_fields:
            raise serializers.ValidationError(
                {field: ["This field is required."] for field in missing_fields}
            )

        with transaction.atomic():
            appointment = get_object_or_404(
                Appointment.objects.select_for_update().select_related(
                    "patient",
                    "doctor_profile__user",
                ),
                pk=appointment_id,
            )
            if appointment.version != request_version:
                return version_conflict_response(appointment.version)

            if appointment.status in Appointment.TERMINAL_STATUSES:
                raise serializers.ValidationError(
                    {"status": ["Terminal appointments cannot be rescheduled."]}
                )
            if appointment.status not in (
                Appointment.Status.NEEDS_RESCHEDULE,
                Appointment.Status.POSTPONED,
            ):
                raise serializers.ValidationError(
                    {
                        "status": [
                            "Only Needs Reschedule or Postponed appointments can be rescheduled."
                        ]
                    }
                )

            old_doctor_profile = appointment.doctor_profile
            old_start_at = appointment.start_at
            old_end_at = appointment.end_at
            previous_status = appointment.status

            data = request.data.copy()
            data.pop("version", None)
            data.pop("reason", None)
            data.pop("note", None)
            serializer = AppointmentSerializer(
                appointment,
                data=data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            try:
                appointment = serializer.save(
                    status=Appointment.Status.SCHEDULED,
                    version=appointment.version + 1,
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc

            log = create_appointment_change_log(
                appointment=appointment,
                action=AppointmentChangeLog.Action.RESCHEDULE,
                previous_status=previous_status,
                new_status=Appointment.Status.SCHEDULED,
                old_doctor_profile=old_doctor_profile,
                new_doctor_profile=appointment.doctor_profile,
                old_start_at=old_start_at,
                old_end_at=old_end_at,
                new_start_at=appointment.start_at,
                new_end_at=appointment.end_at,
                changed_by=request.user,
                reason=reason,
                note=request.data.get("note", ""),
            )
            return Response(
                {
                    "appointment": AppointmentSerializer(appointment).data,
                    "changeLog": AppointmentChangeLogSerializer(log).data,
                }
            )
