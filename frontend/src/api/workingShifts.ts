import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { BackendShift } from "../types/models";

export interface WorkingShiftDTO {
  id: number | string;
  employeeProfileId: number | string;
  userId?: number | string;
  fullName?: string;
  role?: "Doctor" | "Staff";
  specialty?: string;
  dayOfWeek: string;
  startTime: string;
  endTime: string;
  isActive: boolean;
  version: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface WorkingShiftPayload {
  employeeProfileId: number | string;
  dayOfWeek: string;
  startTime: string;
  endTime: string;
  isActive?: boolean;
}

export interface WorkingShiftUpdatePayload extends Partial<WorkingShiftPayload> {
  version: number;
}

interface WorkingShiftListResponse {
  results: WorkingShiftDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method"> & {
  accessToken: string;
};

export async function listWorkingShifts(options: AuthenticatedOptions) {
  const response = await apiClient.get<WorkingShiftDTO[] | WorkingShiftListResponse>("/api/working-shifts/", options);
  return Array.isArray(response) ? response : response.results;
}

export function createWorkingShift(payload: WorkingShiftPayload, options: AuthenticatedOptions) {
  return apiClient.post<WorkingShiftDTO>("/api/working-shifts/", payload, options);
}

export function updateWorkingShift(shiftId: number | string, payload: WorkingShiftUpdatePayload, options: AuthenticatedOptions) {
  return apiClient.patch<WorkingShiftDTO>(`/api/working-shifts/${shiftId}/`, payload, options);
}

export function adaptWorkingShiftDTO(shift: WorkingShiftDTO, shiftIndex = 1): BackendShift {
  return {
    id: String(shift.id),
    staffOrDoctorId: String(shift.employeeProfileId),
    employeeProfileId: String(shift.employeeProfileId),
    employeeName: shift.fullName ?? "",
    dayOfWeek: shift.dayOfWeek,
    shiftName: shiftIndex === 1 ? "Morning" : shiftIndex === 2 ? "Evening" : `Shift ${shiftIndex}`,
    shiftIndex,
    startTime: shift.startTime,
    endTime: shift.endTime,
    isActive: shift.isActive,
    isOnLeave: !shift.isActive,
    version: shift.version,
    createdAt: shift.createdAt,
    updatedAt: shift.updatedAt,
  };
}

export function adaptWorkingShiftList(dtos: WorkingShiftDTO[]) {
  const counts = new Map<string, number>();
  return dtos.map((shift) => {
    const key = `${shift.employeeProfileId}:${shift.dayOfWeek}`;
    const nextIndex = (counts.get(key) ?? 0) + 1;
    counts.set(key, nextIndex);
    return adaptWorkingShiftDTO(shift, nextIndex);
  });
}

export function toWorkingShiftPayload(shift: BackendShift): WorkingShiftPayload {
  return {
    employeeProfileId: shift.employeeProfileId ?? shift.staffOrDoctorId,
    dayOfWeek: shift.dayOfWeek,
    startTime: shift.startTime,
    endTime: shift.endTime,
    isActive: shift.isActive ?? !shift.isOnLeave,
  };
}

export function toWorkingShiftUpdatePayload(shift: BackendShift): WorkingShiftUpdatePayload {
  if (typeof shift.version !== "number") {
    throw new Error("Missing working shift version. Refresh the schedule and try again.");
  }
  return {
    ...toWorkingShiftPayload(shift),
    version: shift.version,
  };
}
