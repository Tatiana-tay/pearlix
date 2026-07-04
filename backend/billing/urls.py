from django.urls import path

from .views import (
    InvoiceCancelView,
    InvoiceDetailView,
    InvoiceListCreateView,
    InvoicePaymentListCreateView,
    PaymentDetailView,
    PaymentListCreateView,
    VisitInvoiceCreateView,
)


urlpatterns = [
    path("invoices/", InvoiceListCreateView.as_view(), name="invoice-list"),
    path("invoices/<int:invoice_id>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path(
        "invoices/<int:invoice_id>/payments/",
        InvoicePaymentListCreateView.as_view(),
        name="invoice-payments",
    ),
    path(
        "invoices/<int:invoice_id>/cancel/",
        InvoiceCancelView.as_view(),
        name="invoice-cancel",
    ),
    path("payments/", PaymentListCreateView.as_view(), name="payment-list"),
    path("payments/<int:payment_id>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("visits/<int:visit_id>/invoice/", VisitInvoiceCreateView.as_view(), name="visit-invoice"),
]
