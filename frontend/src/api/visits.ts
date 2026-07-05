import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { BackendAppointment, BackendVisit } from "../types/models";
import { adaptAppointmentDTO, type AppointmentDTO } from "./appointments";

export interface VisitDTO {
  id: number | string;
  appointmentId: number | string;
  patientId: number | string;
  patientName?: string;
  doctorProfileId: number | string;
  doctorName?: string;
  status: BackendVisit["status"];
  subjectiveNotes?: string;
  objectiveNotes?: string;
  assessmentNotes?: string;
  planNotes?: string;
  generalNotes?: string;
  visitDate?: string;
  startedAt?: string;
  completedAt?: string | null;
  version: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface VisitNotesPayload {
  subjectiveNotes?: string;
  objectiveNotes?: string;
  assessmentNotes?: string;
  planNotes?: string;
  generalNotes?: string;
  version: number;
}

interface VisitListResponse {
  results: VisitDTO[];
}

interface VisitWorkflowResponse {
  visit: VisitDTO;
  appointment: AppointmentDTO;
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method"> & {
  accessToken: string;
};

export async function listVisits(options: AuthenticatedOptions) {
  const response = await apiClient.get<VisitDTO[] | VisitListResponse>("/api/visits/", options);
  return Array.isArray(response) ? response : response.results;
}

export function getActiveVisit(options: AuthenticatedOptions) {
  return apiClient.get<VisitDTO>("/api/visits/active/", options);
}

export function startVisit(appointmentId: number | string, version: number, options: AuthenticatedOptions) {
  return apiClient.post<VisitWorkflowResponse>(`/api/appointments/${appointmentId}/start-visit/`, { version }, options);
}

export function updateVisitNotes(visitId: number | string, payload: VisitNotesPayload, options: AuthenticatedOptions) {
  return apiClient.patch<VisitDTO>(`/api/visits/${visitId}/`, payload, options);
}

export function completeVisit(visitId: number | string, payload: VisitNotesPayload, options: AuthenticatedOptions) {
  return apiClient.post<VisitWorkflowResponse>(`/api/visits/${visitId}/complete/`, payload, options);
}

export function adaptVisitDTO(visit: VisitDTO): BackendVisit {
  return {
    id: String(visit.id),
    appointmentId: String(visit.appointmentId),
    patientId: String(visit.patientId),
    patientName: visit.patientName ?? "",
    doctorId: String(visit.doctorProfileId),
    doctorProfileId: String(visit.doctorProfileId),
    doctorName: visit.doctorName ?? "",
    visitDate: visit.visitDate ?? visit.startedAt ?? "",
    symptomsChiefComplaint: visit.subjectiveNotes ?? "",
    clinicalNotes: visit.objectiveNotes ?? "",
    diagnosisNotes: visit.assessmentNotes ?? "",
    treatmentNotes: visit.planNotes ?? "",
    generalNotes: visit.generalNotes ?? "",
    status: visit.status,
    startedAt: visit.startedAt,
    completedAt: visit.completedAt ?? undefined,
    version: visit.version,
    createdAt: visit.createdAt,
    updatedAt: visit.updatedAt,
  };
}

export function toVisitNotesPayload(visit: BackendVisit): VisitNotesPayload {
  if (typeof visit.version !== "number") {
    throw new Error("Missing visit version. Refresh the active visit and try again.");
  }

  return {
    subjectiveNotes: visit.symptomsChiefComplaint,
    objectiveNotes: visit.clinicalNotes,
    assessmentNotes: visit.diagnosisNotes,
    planNotes: visit.treatmentNotes,
    generalNotes: visit.generalNotes,
    version: visit.version,
  };
}

export function adaptVisitWorkflowResponse(response: VisitWorkflowResponse): { visit: BackendVisit; appointment: BackendAppointment } {
  return {
    visit: adaptVisitDTO(response.visit),
    appointment: adaptAppointmentDTO(response.appointment),
  };
}
