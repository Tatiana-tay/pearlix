from datetime import timezone as datetime_timezone

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsActiveUser, is_admin, is_doctor, is_staff_role
from attachments.models import Attachment
from attachments.views import can_read_attachment
from visits.models import Visit

from .models import AIResult
from .serializers import AIResultFindingSerializer, AIResultSerializer


def can_read_ai_result(user, ai_result):
    return can_read_attachment(user, ai_result.attachment)


def can_create_ai_result(user, attachment):
    if is_staff_role(user):
        return True
    if not is_doctor(user):
        return False
    visit = attachment.visit
    return (
        visit is not None
        and visit.status == Visit.Status.ACTIVE
        and visit.doctor_profile.user_id == user.id
    )


def can_update_ai_result(user, ai_result):
    if is_staff_role(user):
        return True
    if not is_doctor(user):
        return False
    attachment = ai_result.attachment
    visit = attachment.visit
    return (
        visit is not None
        and visit.status == Visit.Status.ACTIVE
        and visit.doctor_profile.user_id == user.id
    )


class AIResultListCreateView(APIView):
    permission_classes = [IsActiveUser]
    path_attachment_id = None

    def get_queryset(self):
        queryset = AIResult.objects.select_related(
            "attachment__patient",
            "attachment__visit__doctor_profile__user",
            "patient",
            "visit__doctor_profile__user",
            "created_by",
        ).prefetch_related("findings")

        if is_doctor(self.request.user):
            queryset = queryset.filter(
                attachment__visit__doctor_profile__user=self.request.user,
            )
        elif not (is_admin(self.request.user) or is_staff_role(self.request.user)):
            raise PermissionDenied("You do not have access to AI results.")

        if self.path_attachment_id is not None:
            queryset = queryset.filter(attachment_id=self.path_attachment_id)

        attachment_id = self.request.query_params.get("attachmentId", "").strip()
        if attachment_id:
            queryset = queryset.filter(
                attachment_id=self._parse_int("attachmentId", attachment_id)
            )

        patient_id = self.request.query_params.get("patientId", "").strip()
        if patient_id:
            queryset = queryset.filter(patient_id=self._parse_int("patientId", patient_id))

        visit_id = self.request.query_params.get("visitId", "").strip()
        if visit_id:
            queryset = queryset.filter(visit_id=self._parse_int("visitId", visit_id))

        result_status = self.request.query_params.get("status", "").strip()
        if result_status:
            valid_statuses = {choice.value for choice in AIResult.Status}
            if result_status not in valid_statuses:
                raise serializers.ValidationError(
                    {"status": ["Enter a valid AI result status."]}
                )
            queryset = queryset.filter(status=result_status)

        model_version = self.request.query_params.get("modelVersion", "").strip()
        if model_version:
            queryset = queryset.filter(model_version=model_version)

        created_from = self._parse_datetime_filter("from")
        created_to = self._parse_datetime_filter("to")
        if created_from and created_to and created_from >= created_to:
            raise serializers.ValidationError(
                {"from": ["From datetime must be before to datetime."]}
            )
        if created_from:
            queryset = queryset.filter(created_at__gte=created_from)
        if created_to:
            queryset = queryset.filter(created_at__lte=created_to)

        return queryset

    def get(self, request, attachment_id=None):
        self.path_attachment_id = attachment_id
        return Response(
            {
                "results": AIResultSerializer(
                    self.get_queryset(),
                    many=True,
                    context={"request": request},
                ).data
            }
        )

    def post(self, request, attachment_id=None):
        data = request.data.copy()
        if attachment_id is not None:
            data["attachmentId"] = attachment_id

        serializer = AIResultSerializer(
            data=data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        attachment = serializer.validated_data["attachment"]
        if not can_create_ai_result(request.user, attachment):
            raise PermissionDenied("You do not have access to create this AI result.")

        ai_result = serializer.save(created_by=request.user)
        return Response(
            AIResultSerializer(
                ai_result,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

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


class AIResultDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, ai_result_id):
        ai_result = self._get_ai_result(ai_result_id)
        if not can_read_ai_result(request.user, ai_result):
            raise PermissionDenied("You do not have access to this AI result.")
        return Response(AIResultSerializer(ai_result, context={"request": request}).data)

    def patch(self, request, ai_result_id):
        ai_result = self._get_ai_result(ai_result_id)
        if not can_update_ai_result(request.user, ai_result):
            raise PermissionDenied("You do not have access to update this AI result.")

        blocked = {
            "attachmentId",
            "patientId",
            "visitId",
            "modelName",
            "modelVersion",
            "findings",
        }
        blocked_fields = sorted(blocked.intersection(request.data.keys()))
        if blocked_fields:
            raise serializers.ValidationError(
                {field: ["This field cannot be changed."] for field in blocked_fields}
            )

        serializer = AIResultSerializer(
            ai_result,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        ai_result = serializer.save()
        return Response(AIResultSerializer(ai_result, context={"request": request}).data)

    def _get_ai_result(self, ai_result_id):
        return get_object_or_404(
            AIResult.objects.select_related(
                "attachment__patient",
                "attachment__visit__doctor_profile__user",
                "patient",
                "visit__doctor_profile__user",
                "created_by",
            ).prefetch_related("findings"),
            pk=ai_result_id,
        )


class AttachmentLatestAIResultView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, attachment_id):
        attachment = get_object_or_404(
            Attachment.objects.select_related(
                "patient",
                "visit__doctor_profile__user",
            ).filter(is_deleted=False),
            pk=attachment_id,
        )
        if not can_read_attachment(request.user, attachment):
            raise PermissionDenied("You do not have access to this attachment.")

        ai_result = (
            AIResult.objects.select_related(
                "attachment__patient",
                "attachment__visit__doctor_profile__user",
                "patient",
                "visit__doctor_profile__user",
                "created_by",
            )
            .prefetch_related("findings")
            .filter(attachment=attachment)
            .first()
        )
        if ai_result is None:
            return Response(
                {"detail": "No AI result for this attachment."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AIResultSerializer(ai_result, context={"request": request}).data)


class AIResultFindingListView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, ai_result_id):
        ai_result = get_object_or_404(
            AIResult.objects.select_related(
                "attachment__patient",
                "attachment__visit__doctor_profile__user",
            ).prefetch_related("findings"),
            pk=ai_result_id,
        )
        if not can_read_ai_result(request.user, ai_result):
            raise PermissionDenied("You do not have access to this AI result.")
        return Response(
            {
                "results": AIResultFindingSerializer(
                    ai_result.findings.all(),
                    many=True,
                ).data
            }
        )
