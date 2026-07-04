from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsActiveUser, is_admin, is_staff_role

from .models import Patient
from .serializers import PatientSerializer


class PatientListCreateView(APIView):
    permission_classes = [IsActiveUser]

    def get_queryset(self):
        queryset = Patient.objects.all()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(email__icontains=search)
                | Q(national_id_or_passport__icontains=search)
            )
        return queryset

    def get(self, request):
        if not (is_admin(request.user) or is_staff_role(request.user)):
            raise PermissionDenied("Doctor patient scope is deferred until appointments exist.")

        serializer = PatientSerializer(self.get_queryset(), many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can create patients.")

        serializer = PatientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PatientDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, patient_id):
        if not (is_admin(request.user) or is_staff_role(request.user)):
            raise PermissionDenied("Doctor patient scope is deferred until appointments exist.")

        patient = get_object_or_404(Patient, pk=patient_id)
        return Response(PatientSerializer(patient).data)

    def patch(self, request, patient_id):
        return self._update(request, patient_id, partial=True)

    def put(self, request, patient_id):
        return self._update(request, patient_id, partial=False)

    def _update(self, request, patient_id, *, partial):
        if not is_staff_role(request.user):
            raise PermissionDenied("Only Staff can update patients.")

        request_version = self._parse_request_version(request.data)

        with transaction.atomic():
            patient = get_object_or_404(Patient.objects.select_for_update(), pk=patient_id)
            if patient.version != request_version:
                return Response(
                    {
                        "detail": "Version conflict",
                        "currentVersion": patient.version,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = PatientSerializer(
                patient,
                data=request.data,
                partial=partial,
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(version=patient.version + 1)
            return Response(serializer.data)

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
