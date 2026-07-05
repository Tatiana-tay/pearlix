import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { BackendInvoice, BackendPayment } from "../types/models";

export interface InvoiceDTO {
  id: number | string;
  visitId: number | string;
  appointmentId?: number | string;
  patientId: number | string;
  patientName?: string;
  doctorProfileId: number | string;
  doctorName?: string;
  createdById?: number | string | null;
  totalAmount: string | number;
  paidAmount: string | number;
  balance: string | number;
  status: BackendInvoice["status"];
  note?: string;
  version: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface InvoicePayload {
  visitId: number | string;
  totalAmount: number;
  note?: string;
}

export interface InvoiceUpdatePayload {
  totalAmount: number;
  version: number;
  reason: string;
}

export interface InvoiceCancelPayload {
  version: number;
  reason: string;
}

export interface PaymentDTO {
  id: number | string;
  invoiceId: number | string;
  amount: string | number;
  method: BackendPayment["paymentMethod"];
  receivedById?: number | string | null;
  receivedByName?: string;
  note?: string;
  createdAt?: string;
}

export interface PaymentPayload {
  invoiceId: number | string;
  amount: number;
  method?: BackendPayment["paymentMethod"];
  note?: string;
}

interface InvoiceListResponse {
  results: InvoiceDTO[];
}

interface PaymentListResponse {
  results: PaymentDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method"> & {
  accessToken: string;
};

export async function listInvoices(options: AuthenticatedOptions) {
  const response = await apiClient.get<InvoiceDTO[] | InvoiceListResponse>("/api/invoices/", options);
  return Array.isArray(response) ? response : response.results;
}

export function createInvoice(payload: InvoicePayload, options: AuthenticatedOptions) {
  return apiClient.post<InvoiceDTO>("/api/invoices/", payload, options);
}

export function updateInvoiceTotal(invoiceId: number | string, payload: InvoiceUpdatePayload, options: AuthenticatedOptions) {
  return apiClient.patch<InvoiceDTO>(`/api/invoices/${invoiceId}/`, payload, options);
}

export function cancelInvoice(invoiceId: number | string, payload: InvoiceCancelPayload, options: AuthenticatedOptions) {
  return apiClient.post<InvoiceDTO>(`/api/invoices/${invoiceId}/cancel/`, payload, options);
}

export async function listPayments(options: AuthenticatedOptions) {
  const response = await apiClient.get<PaymentDTO[] | PaymentListResponse>("/api/payments/", options);
  return Array.isArray(response) ? response : response.results;
}

export function createPayment(payload: PaymentPayload, options: AuthenticatedOptions) {
  return apiClient.post<PaymentDTO>("/api/payments/", payload, options);
}

export function listInvoicePayments(invoiceId: number | string, options: AuthenticatedOptions) {
  return apiClient.get<PaymentListResponse>(`/api/invoices/${invoiceId}/payments/`, options);
}

export function adaptInvoiceDTO(invoice: InvoiceDTO): BackendInvoice {
  return {
    id: String(invoice.id),
    visitId: String(invoice.visitId),
    appointmentId: invoice.appointmentId == null ? undefined : String(invoice.appointmentId),
    patientId: String(invoice.patientId),
    patientName: invoice.patientName ?? "",
    doctorId: String(invoice.doctorProfileId),
    doctorProfileId: String(invoice.doctorProfileId),
    doctorName: invoice.doctorName ?? "",
    invoiceDate: invoice.createdAt?.slice(0, 10) ?? "",
    totalAmount: Number(invoice.totalAmount),
    paidAmount: Number(invoice.paidAmount),
    balance: Number(invoice.balance),
    status: invoice.status,
    note: invoice.note ?? "",
    version: invoice.version,
    createdAt: invoice.createdAt,
    updatedAt: invoice.updatedAt,
  };
}

export function adaptPaymentDTO(payment: PaymentDTO): BackendPayment {
  return {
    id: String(payment.id),
    invoiceId: String(payment.invoiceId),
    amountPaid: Number(payment.amount),
    paymentMethod: payment.method,
    paymentDate: payment.createdAt?.slice(0, 10) ?? "",
    notes: payment.note ?? "",
    receivedById: payment.receivedById == null ? undefined : String(payment.receivedById),
    receivedByName: payment.receivedByName ?? "",
    createdAt: payment.createdAt,
  };
}

export function toInvoiceUpdatePayload(invoice: BackendInvoice, reason = "Updated from billing page."): InvoiceUpdatePayload {
  if (typeof invoice.version !== "number") {
    throw new Error("Missing invoice version. Refresh billing and try again.");
  }
  return {
    totalAmount: invoice.totalAmount,
    version: invoice.version,
    reason,
  };
}

export function toInvoiceCancelPayload(invoice: BackendInvoice, reason = "Cancelled from billing page."): InvoiceCancelPayload {
  if (typeof invoice.version !== "number") {
    throw new Error("Missing invoice version. Refresh billing and try again.");
  }
  return {
    version: invoice.version,
    reason,
  };
}

export function toPaymentPayload(invoice: BackendInvoice, amount: number, note?: string): PaymentPayload {
  return {
    invoiceId: invoice.id,
    amount,
    method: "Cash",
    ...(note?.trim() ? { note: note.trim() } : {}),
  };
}
