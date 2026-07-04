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
from visits.models import Visit

from .models import Invoice
from .serializers import InvoiceSerializer


class InvoiceListCreateView(APIView):
    permission_classes = [IsActiveUser]

    def get_queryset(self):
        queryset = Invoice.objects.select_related(
            "visit__appointment",
            "patient",
            "doctor_profile__user",
            "created_by",
        )

        if is_doctor(self.request.user):
            queryset = queryset.filter(doctor_profile__user=self.request.user)
        elif not (is_admin(self.request.user) or is_staff_role(self.request.user)):
            raise PermissionDenied("You do not have access to invoices.")

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

        visit_id = self.request.query_params.get("visitId", "").strip()
        if visit_id:
            queryset = queryset.filter(visit_id=self._parse_int("visitId", visit_id))

        invoice_status = self.request.query_params.get("status", "").strip()
        if invoice_status:
            valid_statuses = {choice.value for choice in Invoice.Status}
            if invoice_status not in valid_statuses:
                raise serializers.ValidationError(
                    {"status": ["Enter a valid invoice status."]}
                )
            queryset = queryset.filter(status=invoice_status)

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

    def get(self, request):
        return Response({"results": InvoiceSerializer(self.get_queryset(), many=True).data})

    def post(self, request):
        if not is_doctor(request.user):
            raise PermissionDenied("Only Doctor can create invoice handoffs.")

        serializer = InvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._create_invoice(request, serializer.validated_data["visit"], serializer)

    def _create_invoice(self, request, visit, serializer):
        with transaction.atomic():
            visit = get_object_or_404(
                Visit.objects.select_for_update().select_related(
                    "appointment",
                    "patient",
                    "doctor_profile__user",
                ),
                pk=visit.pk,
            )
            if visit.doctor_profile.user_id != request.user.id:
                raise PermissionDenied("You can only create invoices for your own visits.")
            if visit.status != Visit.Status.COMPLETED:
                raise serializers.ValidationError(
                    {"visitId": ["Invoice handoff requires a Completed visit."]}
                )
            if Invoice.objects.filter(visit=visit).exists():
                raise serializers.ValidationError(
                    {"visitId": ["This visit already has an invoice."]}
                )

            try:
                invoice = serializer.save(
                    visit=visit,
                    patient=visit.patient,
                    doctor_profile=visit.doctor_profile,
                    created_by=request.user,
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)

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


class VisitInvoiceCreateView(InvoiceListCreateView):
    def post(self, request, visit_id):
        if not is_doctor(request.user):
            raise PermissionDenied("Only Doctor can create invoice handoffs.")

        data = request.data.copy()
        data["visitId"] = visit_id
        serializer = InvoiceSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return self._create_invoice(request, serializer.validated_data["visit"], serializer)


class InvoiceDetailView(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, invoice_id):
        invoice = get_object_or_404(
            Invoice.objects.select_related(
                "visit__appointment",
                "patient",
                "doctor_profile__user",
                "created_by",
            ),
            pk=invoice_id,
        )
        if not self._can_read_invoice(request.user, invoice):
            raise PermissionDenied("You do not have access to this invoice.")
        return Response(InvoiceSerializer(invoice).data)

    def _can_read_invoice(self, user, invoice):
        return (
            is_admin(user)
            or is_staff_role(user)
            or (is_doctor(user) and invoice.doctor_profile.user_id == user.id)
        )
