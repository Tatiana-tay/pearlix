from django.urls import path

from .views import InvoiceDetailView, InvoiceListCreateView, VisitInvoiceCreateView


urlpatterns = [
    path("invoices/", InvoiceListCreateView.as_view(), name="invoice-list"),
    path("invoices/<int:invoice_id>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("visits/<int:visit_id>/invoice/", VisitInvoiceCreateView.as_view(), name="visit-invoice"),
]
