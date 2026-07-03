import type { Invoice, Payment, Visit } from "../types/models";

export const mockVisits: Visit[] = [
  {
    id: "VIS-001",
    patientId: "PT-1044",
    doctorId: "DOC-001",
    appointmentId: "APT-001",
    visitDate: "2026-01-15",
    status: "Completed",
    Symptoms_Chief_Complaint: "Routine dental review, no active pain.",
    Clinical_Notes: "Healthy gingival tissues with minor plaque buildup.",
    Diagnosis_Notes: "No urgent restorative need.",
    Treatment_Notes: "Professional cleaning completed. Fluoride treatment applied.",
  },
  {
    id: "VIS-002",
    patientId: "PT-2218",
    doctorId: "DOC-002",
    appointmentId: "APT-002",
    visitDate: "2026-02-05",
    status: "Active",
    Symptoms_Chief_Complaint: "Lingering pain around mandibular molar.",
    Clinical_Notes: "Sensitivity to percussion noted. X-ray requested for review.",
    Diagnosis_Notes: "Pulpal involvement suspected pending doctor review.",
    Treatment_Notes: "Root canal access started. Temporary restoration placed.",
  },
  {
    id: "VIS-003",
    patientId: "PT-3302",
    doctorId: "DOC-002",
    appointmentId: "APT-006",
    visitDate: "2025-11-20",
    status: "Completed",
    Symptoms_Chief_Complaint: "Fractured crown on upper premolar.",
    Clinical_Notes: "Existing crown margins compromised.",
    Diagnosis_Notes: "Crown replacement indicated after preparation.",
    Treatment_Notes: "Tooth prepared for new ceramic crown. Temporary crown fitted.",
  },
  {
    id: "VIS-004",
    patientId: "PT-4419",
    doctorId: "DOC-003",
    appointmentId: "APT-003",
    visitDate: "2026-02-01",
    status: "Pending Notes",
    Symptoms_Chief_Complaint: "Routine orthodontic follow-up.",
    Clinical_Notes: "Archwire adjustment completed. Hygiene counseling provided.",
    Diagnosis_Notes: "Expected orthodontic progression.",
    Treatment_Notes: "Adjusted bracket tension and scheduled next follow-up.",
  },
];

export const mockInvoices: Invoice[] = [
  {
    id: "INV-2026-001",
    visitId: "VIS-002",
    patientId: "PT-2218",
    doctorId: "DOC-002",
    invoiceDate: "2026-02-05",
    totalAmount: 1200,
    status: "Paid",
  },
  {
    id: "INV-2026-002",
    visitId: "VIS-001",
    patientId: "PT-1044",
    doctorId: "DOC-001",
    invoiceDate: "2026-01-15",
    totalAmount: 250,
    status: "Paid",
  },
  {
    id: "INV-2026-003",
    visitId: "VIS-003",
    patientId: "PT-3302",
    doctorId: "DOC-002",
    invoiceDate: "2025-11-20",
    totalAmount: 1500,
    status: "Partially Paid",
  },
  {
    id: "INV-2026-004",
    visitId: "VIS-004",
    patientId: "PT-4419",
    doctorId: "DOC-003",
    invoiceDate: "2026-02-01",
    totalAmount: 150,
    status: "Pending",
  },
];

export const mockPayments: Payment[] = [
  {
    id: "PAY-001",
    invoiceId: "INV-2026-001",
    amountPaid: 900,
    paymentDate: "2026-02-05",
    Payment_Method: "Cash",
    notes: "Deposit paid at front desk.",
  },
  {
    id: "PAY-002",
    invoiceId: "INV-2026-001",
    amountPaid: 300,
    paymentDate: "2026-02-06",
    Payment_Method: "Cash",
  },
  {
    id: "PAY-003",
    invoiceId: "INV-2026-002",
    amountPaid: 250,
    paymentDate: "2026-01-15",
    Payment_Method: "Cash",
  },
  {
    id: "PAY-004",
    invoiceId: "INV-2026-003",
    amountPaid: 500,
    paymentDate: "2025-11-20",
    Payment_Method: "Cash",
  },
  {
    id: "PAY-005",
    invoiceId: "INV-2026-003",
    amountPaid: 250,
    paymentDate: "2025-12-05",
    Payment_Method: "Cash",
  },
];

export const getPaymentsForInvoice = (invoiceId: string) =>
  mockPayments.filter((payment) => payment.invoiceId === invoiceId);

export const getPaidTotal = (invoiceId: string) =>
  getPaymentsForInvoice(invoiceId).reduce((total, payment) => total + payment.amountPaid, 0);

export const getRemainingBalance = (invoice: Invoice) => invoice.totalAmount - getPaidTotal(invoice.id);
