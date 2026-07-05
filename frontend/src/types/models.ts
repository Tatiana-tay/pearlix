export type Role = "Admin" | "Doctor" | "Staff";
export type UserStatus = "Active" | "Inactive";
export type ProfileStatus = UserStatus | "On Leave";
export type Gender = "Female" | "Male";

export interface User {
  id: string;
  fullName: string;
  username: string;
  email: string;
  phone: string;
  role: Role;
  status: UserStatus;
  createdAt: string;
  mustChangePassword: boolean;
}

export interface Permission {
  id: string;
  label: string;
  code: string;
}

export interface Patient {
  Patient_ID: string;
  First_Name: string;
  Last_Name: string;
  National_ID_Or_Passport: string;
  Date_Of_Birth: string;
  Gender: Gender;
  Phone_Number: string;
  Medical_Conditions_History: string;
  Blood_Group: string;
  Insurance_Info: string;
  Emergency_Contact: string;
  Address: string;
  Created_At: string;
  email?: string;
}

export interface DoctorProfile {
  Doctor_ID: string;
  User_ID: string;
  Full_Name: string;
  role: "Doctor" | "Staff";
  Specialty: string;
  gender: Gender;
  Phone: string;
  Email: string;
  Status: ProfileStatus;
  avatarUrl?: string;
}

export interface DoctorWorkingHour {
  Working_Hour_ID: string;
  Doctor_ID: string;
  Day_Of_Week: string;
  Start_Time: string;
  End_Time: string;
  Is_On_Leave: boolean;
}

export interface StaffShift {
  id: string;
  userId: string;
  staffOrDoctorId: string;
  dayOfWeek: string;
  shiftName: string;
  shiftIndex: number;
  startTime: string;
  endTime: string;
  isOnLeave: boolean;
}

export type AppointmentStatus =
  | "Scheduled"
  | "Arrived"
  | "Checked-in"
  | "In Visit"
  | "Completed"
  | "Cancelled"
  | "No-show"
  | "Postponed"
  | "Needs Reschedule";

export interface Appointment {
  id: string;
  patientId: string;
  doctorId: string;
  visitType: string;
  date: string;
  time: string;
  durationMinutes: number;
  due: number;
  status: AppointmentStatus;
  notes: string;
}

export interface AvailabilityException {
  exceptionId: string;
  userId: string;
  userRole: "Doctor" | "Staff";
  startDateTime: string;
  endDateTime: string;
  reason: "Leave" | "Sick Leave" | "Personal" | "Training" | "Emergency" | "Other";
  note?: string;
  status: "Active" | "Cancelled";
  createdBy: string;
  createdAt: string;
}

export interface AppointmentChangeLog {
  logId: string;
  appointmentId: string;
  oldDateTime: string;
  newDateTime: string;
  oldDoctorId: string;
  newDoctorId: string;
  reason: "Doctor on leave" | "Patient requested reschedule" | "Clinic schedule adjustment" | "Other";
  changedBy: string;
  changedAt: string;
}

export interface Visit {
  id: string;
  patientId: string;
  doctorId: string;
  appointmentId: string;
  visitDate: string;
  status: "Active" | "Completed" | "Pending Notes";
  Symptoms_Chief_Complaint: string;
  Clinical_Notes: string;
  Diagnosis_Notes: string;
  Treatment_Notes: string;
}

export interface Attachment {
  File_ID: string;
  File_Type: string;
  File_Path: string;
  Upload_Date: string;
  Visit_ID: string;
  Patient_ID: string;
  Doctor_ID: string;
}

export interface AIResult {
  Analysis_ID: string;
  File_ID: string;
  Result_Summary: string;
  Overall_Confidence: number;
  Processed_Date: string;
  Model_Version: string;
  Status: "Pending" | "Processing" | "Completed" | "Failed";
  Overlay_File_Path: string;
}

export interface AIResultFinding {
  Finding_ID: string;
  Analysis_ID: string;
  FDI_Tooth_ID: string;
  Disease_Label: "Caries" | "Deep Caries" | "Impacted" | "Periapical Lesion";
  Confidence_Score: number;
}

export interface Invoice {
  id: string;
  visitId: string;
  patientId: string;
  doctorId: string;
  invoiceDate: string;
  totalAmount: number;
  status: "Pending" | "Partially Paid" | "Paid" | "Cancelled";
}

export interface Payment {
  id: string;
  invoiceId: string;
  amountPaid: number;
  paymentDate: string;
  Payment_Method: "Cash";
  notes?: string;
}

export interface BackendPatient {
  id?: string;
  patientId: string;
  firstName: string;
  lastName: string;
  fullName?: string;
  nationalIdOrPassport: string;
  dateOfBirth: string;
  age?: number;
  gender: Gender;
  phoneNumber: string;
  medicalConditionsHistory: string;
  bloodGroup: string;
  insuranceInfo: string;
  emergencyContact: string;
  address: string;
  createdAt: string;
  updatedAt?: string;
  version?: number;
  email?: string;
}

export interface BackendStaffProfile {
  id: string;
  userId: string;
  fullName: string;
  role: "Doctor" | "Staff";
  specialty?: string;
  gender: Gender;
  email: string;
  phone: string;
  status: ProfileStatus;
  avatarUrl?: string;
  version?: number;
}

export interface BackendShift {
  id: string;
  staffOrDoctorId: string;
  employeeProfileId?: string;
  employeeName?: string;
  dayOfWeek: string;
  shiftName: string;
  shiftIndex: number;
  startTime: string;
  endTime: string;
  isActive?: boolean;
  isOnLeave: boolean;
  version?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface BackendAppointment {
  id: string;
  patientId: string;
  patientName?: string;
  doctorId: string;
  doctorProfileId?: string;
  doctorName?: string;
  startAt?: string;
  endAt?: string;
  visitType: string;
  date: string;
  time: string;
  endDate?: string;
  endTime?: string;
  durationMinutes: number;
  due?: number;
  status: AppointmentStatus;
  notes: string;
  version?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface BackendAvailabilityException {
  id?: string;
  exceptionId: string;
  userId: string;
  employeeProfileId?: string;
  employeeName?: string;
  userRole: AvailabilityException["userRole"];
  startDateTime: string;
  endDateTime: string;
  startAt?: string;
  endAt?: string;
  reason: AvailabilityException["reason"];
  note?: string;
  status: AvailabilityException["status"];
  createdBy: string;
  createdAt: string;
  updatedAt?: string;
  version?: number;
}

export interface BackendAppointmentChangeLog {
  logId: string;
  appointmentId: string;
  oldDateTime: string;
  newDateTime: string;
  oldDoctorId: string;
  newDoctorId: string;
  reason: AppointmentChangeLog["reason"];
  changedBy: string;
  changedAt: string;
}

export interface BackendVisit {
  id: string;
  appointmentId: string;
  patientId: string;
  patientName?: string;
  doctorId: string;
  doctorProfileId?: string;
  doctorName?: string;
  visitDate: string;
  symptomsChiefComplaint: string;
  clinicalNotes: string;
  diagnosisNotes: string;
  treatmentNotes: string;
  generalNotes?: string;
  status: "Active" | "Completed" | "Pending Notes";
  startedAt?: string;
  completedAt?: string;
  version?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface BackendAttachment {
  id: string;
  patientId: string;
  patientName?: string;
  visitId: string;
  filePath: string;
  fileName: string;
  fileType: string;
  mimeType?: string;
  fileSize?: number;
  fileUrl?: string;
  description?: string;
  uploadedBy: string;
  uploadedById?: string;
  uploadedByName?: string;
  uploadedAt: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface BackendAIResult {
  analysisId: string;
  fileId: string;
  attachmentId?: string;
  patientId?: string;
  patientName?: string;
  visitId?: string;
  resultSummary: string;
  overallConfidence: number;
  processedDate: string;
  modelName?: string;
  modelVersion: string;
  status: AIResult["Status"];
  overlayFilePath: string;
  overlayUrl?: string;
  errorMessage?: string;
  findings?: BackendAIResultFinding[];
  createdAt?: string;
  updatedAt?: string;
}

export interface BackendAIResultFinding {
  findingId: string;
  analysisId: string;
  fdiToothId: string;
  diseaseLabel: AIResultFinding["Disease_Label"] | string;
  confidenceScore: number;
  createdAt?: string;
}

export interface BackendInvoice {
  id: string;
  patientId: string;
  patientName?: string;
  visitId: string;
  doctorId: string;
  doctorProfileId?: string;
  doctorName?: string;
  appointmentId?: string;
  invoiceDate: string;
  totalAmount: number;
  paidAmount?: number;
  balance?: number;
  status: Invoice["status"];
  note?: string;
  version?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface BackendPayment {
  id: string;
  invoiceId: string;
  amountPaid: number;
  paymentMethod: Payment["Payment_Method"];
  paymentDate: string;
  notes?: string;
  receivedById?: string;
  receivedByName?: string;
  createdAt?: string;
}
