from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from rest_framework import serializers

from patients.models import Patient
from visits.models import Visit

from .models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(
        source="patient",
        queryset=Patient.objects.all(),
    )
    patientName = serializers.CharField(source="patient.full_name", read_only=True)
    visitId = serializers.PrimaryKeyRelatedField(
        source="visit",
        queryset=Visit.objects.select_related(
            "patient",
            "doctor_profile__user",
        ).all(),
        required=False,
        allow_null=True,
    )
    uploadedById = serializers.IntegerField(source="uploaded_by_id", read_only=True)
    uploadedByName = serializers.CharField(
        source="uploaded_by.full_name",
        read_only=True,
    )
    attachmentType = serializers.ChoiceField(
        source="attachment_type",
        choices=Attachment.AttachmentType.choices,
        required=False,
    )
    originalFilename = serializers.CharField(
        source="original_filename",
        read_only=True,
    )
    contentType = serializers.CharField(source="content_type", read_only=True)
    sizeBytes = serializers.IntegerField(source="size_bytes", read_only=True)
    fileUrl = serializers.SerializerMethodField()
    isDeleted = serializers.BooleanField(source="is_deleted", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Attachment
        fields = (
            "id",
            "patientId",
            "patientName",
            "visitId",
            "uploadedById",
            "uploadedByName",
            "attachmentType",
            "originalFilename",
            "contentType",
            "sizeBytes",
            "fileUrl",
            "description",
            "isDeleted",
            "createdAt",
            "updatedAt",
            "file",
        )
        read_only_fields = (
            "id",
            "patientName",
            "uploadedById",
            "uploadedByName",
            "originalFilename",
            "contentType",
            "sizeBytes",
            "fileUrl",
            "isDeleted",
            "createdAt",
            "updatedAt",
        )
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
        }

    def to_internal_value(self, data):
        if "description" in data or "note" not in data:
            return super().to_internal_value(data)

        if hasattr(data, "dict"):
            incoming = data.dict()
        else:
            incoming = data.copy()
        if "file" in data:
            incoming["file"] = data["file"]
        if "description" not in incoming and "note" in incoming:
            incoming["description"] = incoming["note"]
        return super().to_internal_value(incoming)

    def get_fileUrl(self, obj):
        if obj.is_deleted or not obj.file:
            return None

        path = reverse("attachment-original-url", kwargs={"attachment_id": obj.id})
        request = self.context.get("request")
        if request is None:
            return path
        return request.build_absolute_uri(path)

    def validate(self, attrs):
        if self.instance is None and "file" not in attrs:
            raise serializers.ValidationError({"file": ["This field is required."]})

        if self.instance is not None:
            errors = {}
            if "file" in attrs:
                errors["file"] = ["File replacement is not supported."]
            if "patient" in attrs:
                errors["patientId"] = ["Attachment patient cannot be changed."]
            if "visit" in attrs:
                errors["visitId"] = ["Attachment visit cannot be changed."]
            if errors:
                raise serializers.ValidationError(errors)

        patient = attrs.get("patient") or getattr(self.instance, "patient", None)
        visit = attrs.get("visit") if "visit" in attrs else getattr(self.instance, "visit", None)
        if visit and patient and visit.patient_id != patient.id:
            raise serializers.ValidationError(
                {"visitId": ["Visit must belong to the selected patient."]}
            )

        uploaded_file = attrs.get("file")
        if uploaded_file is not None:
            try:
                Attachment.validate_file_metadata(
                    original_filename=uploaded_file.name,
                    content_type=getattr(uploaded_file, "content_type", ""),
                    size_bytes=uploaded_file.size,
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc

        return attrs

    def create(self, validated_data):
        uploaded_file = validated_data["file"]
        validated_data["original_filename"] = uploaded_file.name
        validated_data["content_type"] = Attachment.normalized_content_type(
            getattr(uploaded_file, "content_type", "")
        )
        validated_data["size_bytes"] = uploaded_file.size

        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
