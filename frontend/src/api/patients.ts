import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { BackendPatient, Gender } from "../types/models";

export interface PatientDTO {
  id: number | string;
  patientId: number | string;
  firstName: string;
  lastName: string;
  fullName?: string;
  gender: Gender;
  dateOfBirth: string;
  age: number;
  phoneNumber: string;
  email?: string;
  nationalIdOrPassport?: string;
  address?: string;
  medicalConditionsHistory?: string;
  bloodGroup?: string;
  insuranceInfo?: string;
  emergencyContact?: string;
  version: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface PatientPayload {
  firstName: string;
  lastName: string;
  gender: Gender;
  dateOfBirth: string;
  phoneNumber: string;
  email?: string;
  nationalIdOrPassport: string;
  address: string;
  medicalConditionsHistory: string;
  bloodGroup: string;
  insuranceInfo: string;
  emergencyContact: string;
}

export interface PatientUpdatePayload extends Partial<PatientPayload> {
  version: number;
}

interface PatientListResponse {
  results: PatientDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method"> & {
  accessToken: string;
};

export async function listPatients(options: AuthenticatedOptions) {
  const response = await apiClient.get<PatientDTO[] | PatientListResponse>("/api/patients/", options);
  return Array.isArray(response) ? response : response.results;
}

export function createPatient(payload: PatientPayload, options: AuthenticatedOptions) {
  return apiClient.post<PatientDTO>("/api/patients/", payload, options);
}

export function getPatient(patientId: number | string, options: AuthenticatedOptions) {
  return apiClient.get<PatientDTO>(`/api/patients/${patientId}/`, options);
}

export function updatePatient(patientId: number | string, payload: PatientUpdatePayload, options: AuthenticatedOptions) {
  return apiClient.patch<PatientDTO>(`/api/patients/${patientId}/`, payload, options);
}

export function adaptPatientDTO(patient: PatientDTO): BackendPatient {
  return {
    id: String(patient.id),
    patientId: String(patient.patientId),
    firstName: patient.firstName,
    lastName: patient.lastName,
    fullName: patient.fullName,
    nationalIdOrPassport: patient.nationalIdOrPassport ?? "",
    dateOfBirth: patient.dateOfBirth,
    age: patient.age,
    gender: patient.gender,
    phoneNumber: patient.phoneNumber,
    medicalConditionsHistory: patient.medicalConditionsHistory ?? "",
    bloodGroup: patient.bloodGroup ?? "",
    insuranceInfo: patient.insuranceInfo ?? "",
    emergencyContact: patient.emergencyContact ?? "",
    address: patient.address ?? "",
    createdAt: patient.createdAt ?? "",
    updatedAt: patient.updatedAt,
    version: patient.version,
    email: patient.email ?? "",
  };
}

export function toPatientPayload(patient: BackendPatient): PatientPayload {
  return {
    firstName: patient.firstName,
    lastName: patient.lastName,
    gender: patient.gender,
    dateOfBirth: patient.dateOfBirth,
    phoneNumber: patient.phoneNumber,
    email: patient.email || undefined,
    nationalIdOrPassport: patient.nationalIdOrPassport,
    address: patient.address,
    medicalConditionsHistory: patient.medicalConditionsHistory,
    bloodGroup: patient.bloodGroup,
    insuranceInfo: patient.insuranceInfo,
    emergencyContact: patient.emergencyContact,
  };
}

export function toPatientUpdatePayload(patient: BackendPatient): PatientUpdatePayload {
  if (typeof patient.version !== "number") {
    throw new Error("Missing patient version. Refresh the patient record and try again.");
  }

  return {
    ...toPatientPayload(patient),
    version: patient.version,
  };
}
