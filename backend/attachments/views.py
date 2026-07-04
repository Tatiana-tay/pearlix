from datetime import timezone as datetime_timezone

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import get_valid_filename
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsActiveUser, is_admin, is_doctor, is_staff_role
from visits.models import Visit

from .models import Attachment
from .serializers import AttachmentSerializer


def can_read_attachment(user, attachment):
    return (
        is_admin(user)
        or is_staff_role(user)
        or (
            is_doctor(user)
            and attachment.visit_id is not None
            and attachment.visit.doctor_profile.user_id == user.id
        )
    )


def can_upload_attachment(user, patient, visit):
    if is_staff_role(user):
        return True
    if not is_doctor(user) or visit is None:
        return False
    return (
        visit.patient_id == patient.id
        and visit.status == Visit.Status.ACTIVE
        and visit.doctor_profile.user_id == user.id
    )


class AttachmentListCreateView(APIView):
    permission_classes = [IsActiveUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    path_visit_id = None

    def get_queryset(self):
        queryset = Attachment.objects.select_related(
            "patient",
            "visit__doctor_profile__user",
            "uploaded_by",
        ).filter(is_deleted=False)

        if is_doctor(self.request.user):
            queryset = queryset.filter(visit__doctor_profile__user=self.request.user)
        elif not (is_admin(self.request.user) or is_staff_role(self.request.user)):
            raise PermissionDenied("You do not have access to attachments.")

        if self.path_visit_id is not None:
            queryset = queryset.filter(visit_id=self.path_visit_id)

        patient_id = self.request.query_params.get("patientId", "").strip()
        if patient_id:
            queryset = queryset.filter(patient_id=self._parse_int("patientId", patient_id))

        visit_id = self.request.query_params.get("visitId", "").strip()
        if visit_id:
            queryset = queryset.filter(visit_id=self._parse_int("visitId", visit_id))

        attachment_type = self.request.query_params.get("attachmentType", "").strip()
        if attachment_type:
            valid_types = {choice.value for choice in Attachment.AttachmentType}
            if attachment_type not in valid_types:
                raise serializers.ValidationError(
                    {"attachmentType": ["Enter a valid attachment type."]}
                )
            queryset = queryset.filter(attachment_type=attachment_type)

        uploaded_by_id = self.request.query_params.get("uploadedById", "").strip()
        if uploaded_by_id:
            queryset = queryset.filter(
                uploaded_by_id=self._parse_int("uploadedById", uploaded_by_id)
            )

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

    def get(self, request, visit_id=None):
        self.path_visit_id = visit_id
        return Response(
            {
                "results": AttachmentSerializer(
                    self.get_queryset(),
                    many=True,
                    context={"request": request},
                ).data
            }
        )

    def post(self, request, visit_id=None):
        data = request.data
        if visit_id is not None:
            data = request.data.dict()
            if "file" in request.data:
                data["file"] = request.data["file"]
            data["visitId"] = visit_id

        serializer = AttachmentSerializer(
            data=data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        patient = serializer.validated_data["patient"]
        visit = serializer.validated_data.get("visit")

        if not can_upload_attachment(request.user, patient, visit):
            raise PermissionDenied("You do not have access to upload this attachment.")

        attachment = serializer.save(uploaded_by=request.user)
        return Response(
            AttachmentSerializer(
                attachment,
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


class AttachmentDetailView(APIView):
    permission_classes = [IsActiveUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, attachment_id):
        attachment = self._get_attachment(attachment_id)
        if not can_read_attachment(request.user, attachment):
            raise PermissionDenied("You do not have access to this attachment.")
        return Response(AttachmentSerializer(attachment, context={"request": request}).data)

    def patch(self, request, attachment_id):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can update attachment metadata.")

        attachment = self._get_attachment(attachment_id)
        serializer = AttachmentSerializer(
            attachment,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save()
        return Response(AttachmentSerializer(attachment, context={"request": request}).data)

    def delete(self, request, attachment_id):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can delete attachments.")

        attachment = self._get_attachment(attachment_id)
        attachment.is_deleted = True
        attachment.updated_at = timezone.now()
        attachment.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _get_attachment(self, attachment_id):
        return get_object_or_404(
            Attachment.objects.select_related(
                "patient",
                "visit__doctor_profile__user",
                "uploaded_by",
            ).filter(is_deleted=False),
            pk=attachment_id,
        )


class AttachmentOriginalUrlView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, attachment_id):
        attachment = get_object_or_404(
            Attachment.objects.select_related(
                "patient",
                "visit__doctor_profile__user",
                "uploaded_by",
            ).filter(is_deleted=False),
            pk=attachment_id,
        )
        if not can_read_attachment(request.user, attachment):
            raise PermissionDenied("You do not have access to this attachment.")
        if not attachment.file:
            raise Http404("Attachment file is not available.")

        try:
            file_handle = attachment.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404("Attachment file is not available.") from exc

        response = FileResponse(file_handle, content_type=attachment.content_type)
        filename = get_valid_filename(attachment.original_filename)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response
