import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { BackendStaffProfile, Gender, ProfileStatus } from "../types/models";

export interface EmployeeProfileDTO {
  id: number | string;
  userId: number | string;
  username?: string;
  fullName: string;
  email: string;
  role: "Doctor" | "Staff";
  status: ProfileStatus;
  specialty?: string | null;
  gender: Gender;
  phone?: string | null;
  avatarUrl?: string | null;
  version?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface EmployeeProfilePayload {
  userId: number | string;
  role: "Doctor" | "Staff";
  specialty?: string;
  gender: Gender;
  status: ProfileStatus;
  phone?: string;
}

export interface EmployeeProfileUpdatePayload {
  role: "Doctor" | "Staff";
  specialty?: string;
  gender: Gender;
  status: ProfileStatus;
  phone?: string;
  version?: number;
}

interface EmployeeProfileListResponse {
  results: EmployeeProfileDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method"> & {
  accessToken: string;
};

export async function listEmployeeProfiles(options: AuthenticatedOptions) {
  const response = await apiClient.get<EmployeeProfileDTO[] | EmployeeProfileListResponse>("/api/employee-profiles/", options);
  return Array.isArray(response) ? response : response.results;
}

export function createEmployeeProfile(payload: EmployeeProfilePayload, options: AuthenticatedOptions) {
  return apiClient.post<EmployeeProfileDTO>("/api/employee-profiles/", payload, options);
}

export function getEmployeeProfile(profileId: number | string, options: AuthenticatedOptions) {
  return apiClient.get<EmployeeProfileDTO>(`/api/employee-profiles/${profileId}/`, options);
}

export function updateEmployeeProfile(profileId: number | string, payload: EmployeeProfileUpdatePayload, options: AuthenticatedOptions) {
  return apiClient.patch<EmployeeProfileDTO>(`/api/employee-profiles/${profileId}/`, payload, options);
}

export function getCurrentEmployeeProfile(options: AuthenticatedOptions) {
  return apiClient.get<EmployeeProfileDTO>("/api/employee-profiles/me/", options);
}

export function adaptEmployeeProfileDTO(profile: EmployeeProfileDTO): BackendStaffProfile {
  return {
    id: String(profile.id),
    userId: String(profile.userId),
    fullName: profile.fullName,
    role: profile.role,
    specialty: profile.specialty ?? "",
    gender: profile.gender,
    email: profile.email,
    phone: profile.phone ?? "",
    status: profile.status,
    avatarUrl: profile.avatarUrl ?? undefined,
    version: profile.version,
  };
}

export function toEmployeeProfilePayload(profile: BackendStaffProfile): EmployeeProfileUpdatePayload {
  return {
    role: profile.role,
    specialty: profile.role === "Doctor" ? profile.specialty || "" : profile.specialty || "",
    gender: profile.gender,
    status: profile.status,
    phone: profile.phone || undefined,
    version: profile.version,
  };
}
