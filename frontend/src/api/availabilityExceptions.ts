import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { AvailabilityException, BackendAvailabilityException } from "../types/models";

export interface AvailabilityExceptionDTO {
  id: number | string;
  employeeProfileId: number | string;
  userId?: number | string;
  fullName?: string;
  role?: "Doctor" | "Staff";
  specialty?: string;
  startAt: string;
  endAt: string;
  reason: AvailabilityException["reason"];
  note?: string;
  status: AvailabilityException["status"];
  version: number;
  createdBy?: number | string | null;
  cancelledAt?: string | null;
  cancelledBy?: number | string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface AvailabilityExceptionPayload {
  employeeProfileId: number | string;
  startAt: string;
  endAt: string;
  reason: AvailabilityException["reason"];
  note?: string;
  status?: AvailabilityException["status"];
}

export interface AvailabilityExceptionUpdatePayload extends Partial<AvailabilityExceptionPayload> {
  version: number;
}

interface AvailabilityExceptionListResponse {
  results: AvailabilityExceptionDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method"> & {
  accessToken: string;
};

export async function listAvailabilityExceptions(options: AuthenticatedOptions) {
  const response = await apiClient.get<AvailabilityExceptionDTO[] | AvailabilityExceptionListResponse>("/api/availability-exceptions/", options);
  return Array.isArray(response) ? response : response.results;
}

export function createAvailabilityException(payload: AvailabilityExceptionPayload, options: AuthenticatedOptions) {
  return apiClient.post<AvailabilityExceptionDTO>("/api/availability-exceptions/", payload, options);
}

export function updateAvailabilityException(exceptionId: number | string, payload: AvailabilityExceptionUpdatePayload, options: AuthenticatedOptions) {
  return apiClient.patch<AvailabilityExceptionDTO>(`/api/availability-exceptions/${exceptionId}/`, payload, options);
}

function toApiDateTime(value: string) {
  if (/Z$|[+-]\d{2}:\d{2}$/.test(value)) {
    return value;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString();
}

export function adaptAvailabilityExceptionDTO(exception: AvailabilityExceptionDTO): BackendAvailabilityException {
  return {
    id: String(exception.id),
    exceptionId: String(exception.id),
    userId: String(exception.employeeProfileId),
    employeeProfileId: String(exception.employeeProfileId),
    employeeName: exception.fullName ?? "",
    userRole: exception.role ?? "Doctor",
    startDateTime: exception.startAt,
    endDateTime: exception.endAt,
    startAt: exception.startAt,
    endAt: exception.endAt,
    reason: exception.reason,
    note: exception.note,
    status: exception.status,
    version: exception.version,
    createdBy: exception.createdBy == null ? "" : String(exception.createdBy),
    createdAt: exception.createdAt ?? "",
    updatedAt: exception.updatedAt,
  };
}

export function toAvailabilityExceptionPayload(exception: BackendAvailabilityException): AvailabilityExceptionPayload {
  const note = exception.note?.trim();
  return {
    employeeProfileId: exception.employeeProfileId ?? exception.userId,
    startAt: toApiDateTime(exception.startAt ?? exception.startDateTime),
    endAt: toApiDateTime(exception.endAt ?? exception.endDateTime),
    reason: exception.reason,
    status: exception.status,
    ...(note ? { note } : {}),
  };
}

export function toAvailabilityExceptionUpdatePayload(exception: BackendAvailabilityException): AvailabilityExceptionUpdatePayload {
  if (typeof exception.version !== "number") {
    throw new Error("Missing availability exception version. Refresh leave and try again.");
  }
  return {
    ...toAvailabilityExceptionPayload(exception),
    version: exception.version,
  };
}
