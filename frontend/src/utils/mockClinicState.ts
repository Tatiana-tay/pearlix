import { adaptAIResult, adaptAttachment, adaptPatient, adaptPayment, adaptStaffProfile, adaptVisit } from "../data/adapters";
import { mockAiResults, mockAttachments } from "../data/mockAi";
import { mockDoctors, mockStaffShifts } from "../data/mockDoctors";
import { mockInvoices, mockPayments, mockVisits } from "../data/mockInvoices";
import { mockPatients } from "../data/mockPatients";
import { mockUsers, rolePermissions } from "../data/mockUsers";
import type {
  BackendAIResult,
  BackendAttachment,
  BackendInvoice,
  BackendPatient,
  BackendPayment,
  BackendShift,
  BackendStaffProfile,
  BackendVisit,
  Invoice,
  Payment,
  Role,
  User,
} from "../types/models";
import { loadRecord, loadRows, saveRecord, saveRows } from "./mockStorage";

const usersKey = "dentalcare.mock.users.v1";
const rolePermissionsKey = "dentalcare.mock.rolePermissions.v1";
const patientsKey = "dentalcare.mock.patients.v1";
const staffProfilesKey = "dentalcare.mock.staffProfiles.v1";
const shiftsKey = "dentalcare.mock.shifts.v1";
const visitsKey = "dentalcare.mock.visits.v1";
const invoicesKey = "dentalcare.mock.invoices.v1";
const paymentsKey = "dentalcare.mock.payments.v1";
const attachmentsKey = "dentalcare.mock.attachments.v1";
const aiResultsKey = "dentalcare.mock.aiResults.v1";
const activeVisitAppointmentKey = "dentalcare.mock.activeVisitAppointmentId.v1";

const initialPatients = mockPatients.map(adaptPatient);
const initialStaffProfiles = mockDoctors.map(adaptStaffProfile);
const initialShifts: BackendShift[] = mockStaffShifts.map((shift) => ({
  id: shift.id,
  staffOrDoctorId: shift.staffOrDoctorId,
  dayOfWeek: shift.dayOfWeek,
  shiftName: shift.shiftName,
  shiftIndex: shift.shiftIndex,
  startTime: shift.startTime,
  endTime: shift.endTime,
  isOnLeave: shift.isOnLeave,
}));
const initialVisits = mockVisits.map(adaptVisit);
const initialPayments = mockPayments.map(adaptPayment);
const initialAttachments = mockAttachments.map(adaptAttachment);
const initialAiResults = mockAiResults.map(adaptAIResult);

export function loadMockUsers() {
  return loadRows<User>(usersKey, mockUsers);
}

export function saveMockUsers(rows: User[]) {
  saveRows(usersKey, rows);
}

export function loadMockRolePermissions() {
  return loadRecord<Record<Role, string[]>>(rolePermissionsKey, rolePermissions);
}

export function saveMockRolePermissions(matrix: Record<Role, string[]>) {
  saveRecord(rolePermissionsKey, matrix);
}

export function loadMockPatients() {
  return loadRows<BackendPatient>(patientsKey, initialPatients);
}

export function saveMockPatients(rows: BackendPatient[]) {
  saveRows(patientsKey, rows);
}

export function loadMockStaffProfiles() {
  return loadRows<BackendStaffProfile>(staffProfilesKey, initialStaffProfiles);
}

export function saveMockStaffProfiles(rows: BackendStaffProfile[]) {
  saveRows(staffProfilesKey, rows);
}

export function getMockStaffProfileForUser(user: User, profiles = loadMockStaffProfiles()) {
  return profiles.find((profile) => profile.userId === user.id)
    ?? profiles.find((profile) => profile.role === user.role && profile.status === "Active")
    ?? null;
}

export function loadMockShifts() {
  return loadRows<BackendShift>(shiftsKey, initialShifts);
}

export function saveMockShifts(rows: BackendShift[]) {
  saveRows(shiftsKey, rows);
}

export function loadMockVisits() {
  return loadRows<BackendVisit>(visitsKey, initialVisits);
}

export function saveMockVisits(rows: BackendVisit[]) {
  saveRows(visitsKey, rows);
}

export function loadMockPayments() {
  return loadRows<BackendPayment>(paymentsKey, initialPayments);
}

export function saveMockPayments(rows: BackendPayment[]) {
  saveRows(paymentsKey, rows);
}

export function loadMockInvoiceBaseRows() {
  return loadRows<Invoice>(invoicesKey, mockInvoices);
}

export function saveMockInvoiceBaseRows(rows: Invoice[]) {
  saveRows(invoicesKey, rows);
}

export function getPaidTotalForInvoice(invoiceId: string, payments = loadMockPayments()) {
  return payments
    .filter((payment) => payment.invoiceId === invoiceId)
    .reduce((total, payment) => total + payment.amountPaid, 0);
}

export function calculateInvoiceStatus(totalAmount: number, paidAmount: number, cancelled = false): Invoice["status"] {
  if (cancelled) return "Cancelled";
  if (paidAmount <= 0) return "Pending";
  if (paidAmount < totalAmount) return "Partially Paid";
  return "Paid";
}

export function toBackendInvoice(invoice: Invoice, payments = loadMockPayments()): BackendInvoice {
  const paidAmount = getPaidTotalForInvoice(invoice.id, payments);
  const status = calculateInvoiceStatus(invoice.totalAmount, paidAmount, invoice.status === "Cancelled");
  return {
    ...invoice,
    paidAmount,
    balance: Math.max(invoice.totalAmount - paidAmount, 0),
    status,
  };
}

export function loadMockInvoices() {
  const payments = loadMockPayments();
  return loadMockInvoiceBaseRows().map((invoice) => toBackendInvoice(invoice, payments));
}

export function saveMockInvoices(rows: BackendInvoice[]) {
  saveMockInvoiceBaseRows(rows.map((invoice) => ({
    id: invoice.id,
    visitId: invoice.visitId,
    patientId: invoice.patientId,
    doctorId: invoice.doctorId,
    invoiceDate: invoice.invoiceDate,
    totalAmount: invoice.totalAmount,
    status: invoice.status,
  })));
}

export function recordMockPayment(invoice: BackendInvoice, payment: Omit<BackendPayment, "id">) {
  if (invoice.status === "Cancelled") {
    return invoice;
  }

  const nextPayments = [
    ...loadMockPayments(),
    {
      ...payment,
      id: `PAY-${Date.now().toString().slice(-6)}`,
    },
  ];
  saveMockPayments(nextPayments);

  const invoiceBaseRows = loadMockInvoiceBaseRows().map((item) => {
    if (item.id !== invoice.id) return item;
    const paidAmount = getPaidTotalForInvoice(invoice.id, nextPayments);
    return {
      ...item,
      status: calculateInvoiceStatus(item.totalAmount, paidAmount),
    };
  });
  saveMockInvoiceBaseRows(invoiceBaseRows);
  return toBackendInvoice(invoiceBaseRows.find((item) => item.id === invoice.id) ?? invoice, nextPayments);
}

export function loadMockAttachments() {
  return loadRows<BackendAttachment>(attachmentsKey, initialAttachments);
}

export function saveMockAttachments(rows: BackendAttachment[]) {
  saveRows(attachmentsKey, rows);
}

export function loadMockAIResults() {
  return loadRows<BackendAIResult>(aiResultsKey, initialAiResults);
}

export function saveMockAIResults(rows: BackendAIResult[]) {
  saveRows(aiResultsKey, rows);
}

export function saveActiveVisitAppointmentId(appointmentId: string | null) {
  if (typeof window === "undefined") return;
  if (!appointmentId) {
    window.localStorage.removeItem(activeVisitAppointmentKey);
    return;
  }
  window.localStorage.setItem(activeVisitAppointmentKey, appointmentId);
}

export function loadActiveVisitAppointmentId() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(activeVisitAppointmentKey);
}

export function toBackendPayment(payment: Payment) {
  return adaptPayment(payment);
}
