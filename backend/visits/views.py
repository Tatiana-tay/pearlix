from datetime import timezone as datetime_timezone

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
from scheduling.models import Appointment, AppointmentChangeLog
from scheduling.serializers import AppointmentSerializer

from .models import Visit
from .serializers import VisitSerializer


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


def workflow_reason(data):
    value = data.get("reason") or data.get("note") or ""
    return str(value).strip()


def create_visit_status_log(*, appointment, action, previous_status, new_status, user, visit, reason):
    return AppointmentChangeLog.objects.create(
        appointment=appointment,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        changed_by=user,
        reason=reason,
        metadata={"visitId": visit.id},
    )


class VisitListView(APIView):
    permission_classes = [IsActiveUser]

    def get_queryset(self):
        queryset = Visit.objects.select_related(
            "appointment",
            "patient",
            "doctor_profile__user",
        )

        if is_doctor(self.request.user):
            queryset = queryset.filter(doctor_profile__user=self.request.user)
        elif not (is_admin(self.request.user) or is_staff_role(self.request.user)):
            raise PermissionDenied("You do not have access to visits.")

        patient_id = self.request.query_params.get("patientId", "").strip()
        if patient_id:
            queryset = queryset.filter(patient_id=self._parse_int("patientId", patient_id))

        doctor_profile_id = (
            self.request.query_params.get("doctorProfileId", "").strip()
            or self.request.query_params.get("doctorId", "").strip()
        )
        if doctor_profile_id:
            queryset = queryset.filter(
                doctor_profile_id=self._parse_int("doctorProfileId", doctor_profile_id)
            )

        appointment_id = self.request.query_params.get("appointmentId", "").strip()
        if appointment_id:
            queryset = queryset.filter(
                appointment_id=self._parse_int("appointmentId", appointment_id)
            )

        visit_status = self.request.query_params.get("status", "").strip()
        if visit_status:
            valid_statuses = {choice.value for choice in Visit.Status}
            if visit_status not in valid_statuses:
                raise serializers.ValidationError(
                    {"status": ["Enter a valid visit status."]}
                )
            queryset = queryset.filter(status=visit_status)

        started_from = self._parse_datetime_filter("from")
        started_to = self._parse_datetime_filter("to")
        if started_from and started_to and started_from >= started_to:
            raise serializers.ValidationError(
                {"from": ["From datetime must be before to datetime."]}
            )
        if started_from:
            queryset = queryset.filter(started_at__gte=started_from)
        if started_to:
            queryset = queryset.filter(started_at__lte=started_to)

        return queryset

    def get(self, request):
        return Response({"results": VisitSerializer(self.get_queryset(), many=True).data})

    def _parse_int(self, name, value):
        try:
            return int(value)
        except ValueError as exc:
            raise serializers.ValidationError(
                {name: ["A valid integer is required."]}
            ) from exc

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


class VisitStartView(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, appointment_id=None):
        if not is_doctor(request.user):
            raise PermissionDenied("Only Doctor can start visits.")

        if appointment_id is None:
            if "appointmentId" not in request.data:
                raise serializers.ValidationError(
                    {"appointmentId": ["This field is required."]}
                )
            try:
                appointment_id = int(request.data["appointmentId"])
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    {"appointmentId": ["A valid integer is required."]}
                ) from exc

        request_version = parse_request_version(request.data)
        reason = workflow_reason(request.data)

        with transaction.atomic():
            appointment = get_object_or_404(
                Appointment.objects.select_for_update().select_related(
                    "patient",
                    "doctor_profile__user",
                ),
                pk=appointment_id,
            )
            if appointment.doctor_profile.user_id != request.user.id:
                raise PermissionDenied("You can only start your own appointments.")
            if appointment.version != request_version:
                return version_conflict_response(appointment.version)
            if appointment.status != Appointment.Status.CHECKED_IN:
                raise serializers.ValidationError(
                    {"status": ["Visit can start only from a Checked-in appointment."]}
                )
            if Visit.objects.filter(appointment=appointment).exists():
                raise serializers.ValidationError(
                    {"appointmentId": ["This appointment already has a visit."]}
                )
            if Visit.objects.filter(
                doctor_profile=appointment.doctor_profile,
                status=Visit.Status.ACTIVE,
            ).exists():
                raise serializers.ValidationError(
                    {"doctorProfileId": ["Doctor already has an active visit."]}
                )

            now = timezone.now()
            visit = Visit.objects.create(
                appointment=appointment,
                patient=appointment.patient,
                doctor_profile=appointment.doctor_profile,
                started_at=now,
            )
            previous_status = appointment.status
            Appointment.objects.filter(pk=appointment.pk).update(
                status=Appointment.Status.IN_VISIT,
                version=appointment.version + 1,
                updated_at=now,
            )
            appointment.status = Appointment.Status.IN_VISIT
            appointment.version += 1
            appointment.refresh_from_db()
            create_visit_status_log(
                appointment=appointment,
                action=AppointmentChangeLog.Action.START_VISIT,
                previous_status=previous_status,
                new_status=Appointment.Status.IN_VISIT,
                user=request.user,
                visit=visit,
                reason=reason,
            )
            return Response(
                {
                    "appointment": AppointmentSerializer(appointment).data,
                    "visit": VisitSerializer(visit).data,
                },
                status=status.HTTP_201_CREATED,
            )


class VisitActiveView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        if not is_doctor(request.user):
            raise PermissionDenied("Only Doctor can access active visits.")

        queryset = Visit.objects.select_related(
            "appointment",
            "patient",
            "doctor_profile__user",
        ).filter(
            doctor_profile__user=request.user,
            status=Visit.Status.ACTIVE,
        )

        appointment_id = request.query_params.get("appointmentId", "").strip()
        if appointment_id:
            try:
                appointment_id = int(appointment_id)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"appointmentId": ["A valid integer is required."]}
                ) from exc
            queryset = queryset.filter(appointment_id=appointment_id)

        visit = queryset.first()
        if visit is None:
            return Response(
                {"detail": "No active visit."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(VisitSerializer(visit).data)


class VisitDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, visit_id):
        visit = self._get_visit(visit_id)
        if not self._can_read_visit(request.user, visit):
            raise PermissionDenied("You do not have access to this visit.")
        return Response(VisitSerializer(visit).data)

    def patch(self, request, visit_id):
        if not is_doctor(request.user):
            raise PermissionDenied("Only Doctor can update visit notes.")

        request_version = parse_request_version(request.data)

        with transaction.atomic():
            visit = get_object_or_404(
                Visit.objects.select_for_update().select_related(
                    "appointment",
                    "patient",
                    "doctor_profile__user",
                ),
                pk=visit_id,
            )
            if visit.doctor_profile.user_id != request.user.id:
                raise PermissionDenied("You can only update your own visits.")
            if visit.version != request_version:
                return version_conflict_response(visit.version)
            if visit.status != Visit.Status.ACTIVE:
                raise serializers.ValidationError(
                    {"status": ["Completed visit notes cannot be changed."]}
                )

            serializer = VisitSerializer(visit, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            try:
                visit = serializer.save(version=visit.version + 1)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            return Response(VisitSerializer(visit).data)

    def _get_visit(self, visit_id):
        return get_object_or_404(
            Visit.objects.select_related(
                "appointment",
                "patient",
                "doctor_profile__user",
            ),
            pk=visit_id,
        )

    def _can_read_visit(self, user, visit):
        return (
            is_admin(user)
            or is_staff_role(user)
            or (is_doctor(user) and visit.doctor_profile.user_id == user.id)
        )


class VisitCompleteView(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, visit_id):
        if not is_doctor(request.user):
            raise PermissionDenied("Only Doctor can complete visits.")

        request_version = parse_request_version(request.data)
        reason = workflow_reason(request.data)

        with transaction.atomic():
            visit = get_object_or_404(
                Visit.objects.select_for_update().select_related(
                    "appointment",
                    "patient",
                    "doctor_profile__user",
                ),
                pk=visit_id,
            )
            appointment = Appointment.objects.select_for_update().get(
                pk=visit.appointment_id,
            )

            if visit.doctor_profile.user_id != request.user.id:
                raise PermissionDenied("You can only complete your own visits.")
            if visit.version != request_version:
                return version_conflict_response(visit.version)
            if visit.status != Visit.Status.ACTIVE:
                raise serializers.ValidationError(
                    {"status": ["Only Active visits can be completed."]}
                )
            if appointment.status != Appointment.Status.IN_VISIT:
                raise serializers.ValidationError(
                    {"appointment": ["Visit appointment must be In Visit."]}
                )

            serializer = VisitSerializer(visit, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            now = timezone.now()
            try:
                visit = serializer.save(
                    status=Visit.Status.COMPLETED,
                    completed_at=now,
                    version=visit.version + 1,
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc

            previous_status = appointment.status
            Appointment.objects.filter(pk=appointment.pk).update(
                status=Appointment.Status.COMPLETED,
                version=appointment.version + 1,
                updated_at=now,
            )
            appointment.status = Appointment.Status.COMPLETED
            appointment.version += 1
            appointment.refresh_from_db()
            create_visit_status_log(
                appointment=appointment,
                action=AppointmentChangeLog.Action.COMPLETE_VISIT,
                previous_status=previous_status,
                new_status=Appointment.Status.COMPLETED,
                user=request.user,
                visit=visit,
                reason=reason,
            )
            return Response(
                {
                    "visit": VisitSerializer(visit).data,
                    "appointment": AppointmentSerializer(appointment).data,
                }
            )
