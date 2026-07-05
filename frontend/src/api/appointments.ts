import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { AppointmentStatus, BackendAppointment } from "../types/models";

export interface AppointmentDTO {
  id: number | string;
  patientId: number | string;
  patientName?: string;
  doctorProfileId: number | string;
  doctorName?: string;
  startAt: string;
  endAt: string;
  durationMinutes: number;
  visitType: string;
  status: AppointmentStatus;
  notes?: string;
  version: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface AppointmentPayload {
  patientId: number | string;
  doctorProfileId: number | string;
  startAt: string;
  endAt: string;
  durationMinutes: number;
  visitType: string;
  notes?: string;
}

export interface AppointmentUpdatePayload extends Partial<AppointmentPayload> {
  version: number;
}

export type AppointmentWorkflowAction = "arrive" | "check-in" | "cancel" | "no-show" | "postpone" | "mark-needs-reschedule";

interface AppointmentListResponse {
  results: AppointmentDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method"> & {
  accessToken: string;
};

export async function listAppointments(options: AuthenticatedOptions) {
  const response = await apiClient.get<AppointmentDTO[] | AppointmentListResponse>("/api/appointments/", options);
  return Array.isArray(response) ? response : response.results;
}

export function createAppointment(payload: AppointmentPayload, options: AuthenticatedOptions) {
  return apiClient.post<AppointmentDTO>("/api/appointments/", payload, options);
}

export function updateAppointment(appointmentId: number | string, payload: AppointmentUpdatePayload, options: AuthenticatedOptions) {
  return apiClient.patch<AppointmentDTO>(`/api/appointments/${appointmentId}/`, payload, options);
}

export function runAppointmentWorkflowAction(
  appointmentId: number | string,
  action: AppointmentWorkflowAction,
  payload: { version: number },
  options: AuthenticatedOptions,
) {
  return apiClient.post<AppointmentDTO>(`/api/appointments/${appointmentId}/${action}/`, payload, options);
}

export function rescheduleAppointment(
  appointmentId: number | string,
  payload: AppointmentUpdatePayload & { reason?: string; note?: string },
  options: AuthenticatedOptions,
) {
  return apiClient.post<{ appointment: AppointmentDTO }>(`/api/appointments/${appointmentId}/reschedule/`, payload, options);
}

function localDateTimeParts(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return { date: value.slice(0, 10), time: value.slice(11, 16) };
  }

  return {
    date: `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-${String(parsed.getDate()).padStart(2, "0")}`,
    time: `${String(parsed.getHours()).padStart(2, "0")}:${String(parsed.getMinutes()).padStart(2, "0")}`,
  };
}

function toApiDateTime(date: string, time: string) {
  return new Date(`${date}T${time}`).toISOString();
}

function addMinutes(date: string, time: string, minutes: number) {
  const parsed = new Date(`${date}T${time}`);
  parsed.setMinutes(parsed.getMinutes() + minutes);
  return parsed.toISOString();
}

export function adaptAppointmentDTO(appointment: AppointmentDTO): BackendAppointment {
  const start = localDateTimeParts(appointment.startAt);
  const end = localDateTimeParts(appointment.endAt);
  return {
    id: String(appointment.id),
    patientId: String(appointment.patientId),
    patientName: appointment.patientName ?? "",
    doctorId: String(appointment.doctorProfileId),
    doctorProfileId: String(appointment.doctorProfileId),
    doctorName: appointment.doctorName ?? "",
    startAt: appointment.startAt,
    endAt: appointment.endAt,
    visitType: appointment.visitType,
    date: start.date,
    time: start.time,
    endDate: end.date,
    endTime: end.time,
    durationMinutes: appointment.durationMinutes,
    status: appointment.status,
    notes: appointment.notes ?? "",
    version: appointment.version,
    createdAt: appointment.createdAt,
    updatedAt: appointment.updatedAt,
  };
}

export function toAppointmentPayload(appointment: BackendAppointment): AppointmentPayload {
  const startAt = appointment.startAt ?? toApiDateTime(appointment.date, appointment.time);
  const endAt = appointment.endAt ?? addMinutes(appointment.date, appointment.time, appointment.durationMinutes);
  return {
    patientId: appointment.patientId,
    doctorProfileId: appointment.doctorProfileId ?? appointment.doctorId,
    startAt,
    endAt,
    durationMinutes: appointment.durationMinutes,
    visitType: appointment.visitType,
    notes: appointment.notes?.trim() || undefined,
  };
}

export function toAppointmentUpdatePayload(appointment: BackendAppointment): AppointmentUpdatePayload {
  if (typeof appointment.version !== "number") {
    throw new Error("Missing appointment version. Refresh the appointment and try again.");
  }

  return {
    ...toAppointmentPayload(appointment),
    version: appointment.version,
  };
}

export function toAppointmentStatusPayload(appointment: BackendAppointment, _status?: AppointmentStatus): { version: number } {
  if (typeof appointment.version !== "number") {
    throw new Error("Missing appointment version. Refresh the appointment and try again.");
  }

  return {
    version: appointment.version,
  };
}
