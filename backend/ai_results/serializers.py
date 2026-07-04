from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from attachments.models import Attachment

from .models import AIResult, AIResultFinding


class AIResultFindingSerializer(serializers.ModelSerializer):
    toothFdi = serializers.CharField(source="tooth_fdi")
    diseaseLabel = serializers.CharField(source="disease_label")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AIResultFinding
        fields = (
            "id",
            "toothFdi",
            "diseaseLabel",
            "confidence",
            "bbox",
            "mask",
            "metadata",
            "createdAt",
        )
        read_only_fields = ("id", "createdAt")
        extra_kwargs = {
            "bbox": {"required": False, "allow_null": True},
            "mask": {"required": False, "allow_null": True},
            "metadata": {"required": False},
        }

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc


class AIResultSerializer(serializers.ModelSerializer):
    attachmentId = serializers.PrimaryKeyRelatedField(
        source="attachment",
        queryset=Attachment.objects.select_related(
            "patient",
            "visit__doctor_profile__user",
        ).filter(is_deleted=False),
    )
    patientId = serializers.IntegerField(source="patient_id", read_only=True)
    patientName = serializers.CharField(source="patient.full_name", read_only=True)
    visitId = serializers.IntegerField(source="visit_id", read_only=True)
    resultSummary = serializers.CharField(
        source="result_summary",
        required=False,
        allow_blank=True,
    )
    modelName = serializers.CharField(source="model_name")
    modelVersion = serializers.CharField(source="model_version")
    overallConfidence = serializers.FloatField(
        source="overall_confidence",
        required=False,
        allow_null=True,
    )
    overlayUrl = serializers.CharField(
        source="overlay_url",
        required=False,
        allow_blank=True,
    )
    errorMessage = serializers.CharField(
        source="error_message",
        required=False,
        allow_blank=True,
    )
    findings = AIResultFindingSerializer(many=True, required=False)
    createdById = serializers.IntegerField(source="created_by_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = AIResult
        fields = (
            "id",
            "attachmentId",
            "patientId",
            "patientName",
            "visitId",
            "status",
            "resultSummary",
            "modelName",
            "modelVersion",
            "overallConfidence",
            "overlayUrl",
            "errorMessage",
            "metadata",
            "findings",
            "createdById",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "patientId",
            "patientName",
            "visitId",
            "createdById",
            "createdAt",
            "updatedAt",
        )
        extra_kwargs = {
            "metadata": {"required": False},
        }

    def validate_overallConfidence(self, value):
        if value is not None and not (0 <= value <= 1):
            raise serializers.ValidationError(
                "Overall confidence must be between 0 and 1."
            )
        return value

    def validate_metadata(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a JSON object.")
        return value

    def create(self, validated_data):
        findings_data = validated_data.pop("findings", [])
        attachment = validated_data["attachment"]
        validated_data["patient"] = attachment.patient
        validated_data["visit"] = attachment.visit

        try:
            with transaction.atomic():
                ai_result = AIResult.objects.create(**validated_data)
                for finding_data in findings_data:
                    AIResultFinding.objects.create(
                        ai_result=ai_result,
                        **finding_data,
                    )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return ai_result

    def update(self, instance, validated_data):
        validated_data.pop("findings", None)
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
