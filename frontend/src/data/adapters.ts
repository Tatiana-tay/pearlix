import { mockAiFindings, mockAiResults, mockAttachments } from "./mockAi";
import { mockAppointmentChangeLogs, mockAppointments, mockAvailabilityExceptions } from "./mockAppointments";
import { getPaidTotal, getPaymentsForInvoice, getRemainingBalance, mockInvoices, mockVisits } from "./mockInvoices";
import { getShiftsForProfile, mockDoctors } from "./mockDoctors";
import { mockPatients } from "./mockPatients";
import type {
  AIResult,
  AIResultFinding,
  Appointment,
  AppointmentChangeLog,
  Attachment,
  BackendAIResult,
  BackendAIResultFinding,
  BackendAppointment,
  BackendAppointmentChangeLog,
  BackendAttachment,
  BackendAvailabilityException,
  BackendInvoice,
  BackendPatient,
  BackendPayment,
  BackendShift,
  BackendStaffProfile,
  BackendVisit,
  DoctorProfile,
  Invoice,
  Patient,
  Payment,
  StaffShift,
  AvailabilityException,
  Visit,
} from "../types/models";

export const adaptPatient = (patient: Patient): BackendPatient => ({
  patientId: patient.Patient_ID,
  firstName: patient.First_Name,
  lastName: patient.Last_Name,
  nationalIdOrPassport: patient.National_ID_Or_Passport,
  dateOfBirth: patient.Date_Of_Birth,
  gender: patient.Gender,
  phoneNumber: patient.Phone_Number,
  medicalConditionsHistory: patient.Medical_Conditions_History,
  bloodGroup: patient.Blood_Group,
  insuranceInfo: patient.Insurance_Info,
  emergencyContact: patient.Emergency_Contact,
  address: patient.Address,
  createdAt: patient.Created_At,
  email: patient.email,
});

export const adaptStaffProfile = (profile: DoctorProfile): BackendStaffProfile => ({
  id: profile.Doctor_ID,
  userId: profile.User_ID,
  fullName: profile.Full_Name,
  role: profile.role,
  specialty: profile.Specialty,
  gender: profile.gender,
  email: profile.Email,
  phone: profile.Phone,
  status: profile.Status,
  avatarUrl: profile.avatarUrl,
});

export const adaptShift = (shift: StaffShift, staffOrDoctorId: string): BackendShift => ({
  id: shift.id,
  staffOrDoctorId,
  dayOfWeek: shift.dayOfWeek,
  shiftName: shift.shiftName,
  shiftIndex: shift.shiftIndex,
  startTime: shift.startTime,
  endTime: shift.endTime,
  isOnLeave: shift.isOnLeave,
});

export const adaptAppointment = (appointment: Appointment): BackendAppointment => ({
  id: appointment.id,
  patientId: appointment.patientId,
  doctorId: appointment.doctorId,
  visitType: appointment.visitType,
  date: appointment.date,
  time: appointment.time,
  durationMinutes: appointment.durationMinutes,
  due: appointment.due,
  status: appointment.status,
  notes: appointment.notes,
});

export const adaptAvailabilityException = (exception: AvailabilityException): BackendAvailabilityException => ({
  exceptionId: exception.exceptionId,
  userId: exception.userId,
  userRole: exception.userRole,
  startDateTime: exception.startDateTime,
  endDateTime: exception.endDateTime,
  reason: exception.reason,
  note: exception.note,
  status: exception.status,
  createdBy: exception.createdBy,
  createdAt: exception.createdAt,
});

export const adaptAppointmentChangeLog = (log: AppointmentChangeLog): BackendAppointmentChangeLog => ({
  logId: log.logId,
  appointmentId: log.appointmentId,
  oldDateTime: log.oldDateTime,
  newDateTime: log.newDateTime,
  oldDoctorId: log.oldDoctorId,
  newDoctorId: log.newDoctorId,
  reason: log.reason,
  changedBy: log.changedBy,
  changedAt: log.changedAt,
});

export const adaptVisit = (visit: Visit): BackendVisit => ({
  id: visit.id,
  appointmentId: visit.appointmentId,
  patientId: visit.patientId,
  doctorId: visit.doctorId,
  visitDate: visit.visitDate,
  symptomsChiefComplaint: visit.Symptoms_Chief_Complaint,
  clinicalNotes: visit.Clinical_Notes,
  diagnosisNotes: visit.Diagnosis_Notes,
  treatmentNotes: visit.Treatment_Notes,
  status: visit.status,
});

export const adaptAttachment = (attachment: Attachment): BackendAttachment => ({
  id: attachment.File_ID,
  patientId: attachment.Patient_ID,
  visitId: attachment.Visit_ID,
  filePath: attachment.File_Path,
  fileName: attachment.File_Path,
  fileType: attachment.File_Type,
  uploadedBy: attachment.Doctor_ID,
  uploadedAt: attachment.Upload_Date,
});

export const adaptAIResult = (result: AIResult): BackendAIResult => ({
  analysisId: result.Analysis_ID,
  fileId: result.File_ID,
  resultSummary: result.Result_Summary,
  overallConfidence: result.Overall_Confidence,
  processedDate: result.Processed_Date,
  modelVersion: result.Model_Version,
  status: result.Status,
  overlayFilePath: result.Overlay_File_Path,
});

export const adaptAIResultFinding = (finding: AIResultFinding): BackendAIResultFinding => ({
  findingId: finding.Finding_ID,
  analysisId: finding.Analysis_ID,
  fdiToothId: finding.FDI_Tooth_ID,
  diseaseLabel: finding.Disease_Label,
  confidenceScore: finding.Confidence_Score,
});

export const adaptInvoice = (invoice: Invoice): BackendInvoice => ({
  id: invoice.id,
  patientId: invoice.patientId,
  visitId: invoice.visitId,
  doctorId: invoice.doctorId,
  invoiceDate: invoice.invoiceDate,
  totalAmount: invoice.totalAmount,
  paidAmount: getPaidTotal(invoice.id),
  balance: getRemainingBalance(invoice),
  status: invoice.status,
});

export const adaptPayment = (payment: Payment): BackendPayment => ({
  id: payment.id,
  invoiceId: payment.invoiceId,
  amountPaid: payment.amountPaid,
  paymentMethod: payment.Payment_Method,
  paymentDate: payment.paymentDate,
  notes: payment.notes,
});

export const patients = mockPatients.map(adaptPatient);
export const staffProfiles = mockDoctors.map(adaptStaffProfile);
export const appointments = mockAppointments.map(adaptAppointment);
export const availabilityExceptions = mockAvailabilityExceptions.map(adaptAvailabilityException);
export const appointmentChangeLogs = mockAppointmentChangeLogs.map(adaptAppointmentChangeLog);
export const visits = mockVisits.map(adaptVisit);
export const attachments = mockAttachments.map(adaptAttachment);
export const aiResults = mockAiResults.map(adaptAIResult);
export const aiFindings = mockAiFindings.map(adaptAIResultFinding);
export const invoices = mockInvoices.map(adaptInvoice);

export const getPatientById = (patientId?: string) =>
  patients.find((patient) => patient.patientId === patientId);

export const getStaffProfileById = (profileId?: string) =>
  staffProfiles.find((profile) => profile.id === profileId);

export const getVisitById = (visitId?: string) =>
  visits.find((visit) => visit.id === visitId);

export const getVisitsForPatient = (patientId: string) =>
  visits.filter((visit) => visit.patientId === patientId);

export const getAppointmentsForPatient = (patientId: string) =>
  appointments.filter((appointment) => appointment.patientId === patientId);

export const getAttachmentsForPatient = (patientId: string) =>
  attachments.filter((attachment) => attachment.patientId === patientId);

export const getAIResultByFileId = (fileId: string) =>
  aiResults.find((result) => result.fileId === fileId);

export const getAIFindingsByAnalysisId = (analysisId?: string) =>
  analysisId ? aiFindings.filter((finding) => finding.analysisId === analysisId) : [];

export const getPaymentsForInvoiceRecord = (invoiceId: string) =>
  getPaymentsForInvoice(invoiceId).map(adaptPayment);

export const getShiftsForStaffProfile = (profileId: string) =>
  getShiftsForProfile(profileId).map((shift) => adaptShift(shift, profileId));

export const patientDisplayName = (patient: BackendPatient) =>
  `${patient.firstName} ${patient.lastName}`.trim();
