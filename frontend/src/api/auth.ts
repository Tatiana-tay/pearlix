import { apiClient } from "./client";
import type { RequestOptions, Role } from "./types";

export interface AuthUserDTO {
  id: string;
  username: string;
  email: string;
  phone: string;
  fullName: string;
  role: Role;
  status: "Active" | "Inactive";
  createdAt: string;
  mustChangePassword: boolean;
}

export interface LoginRequestDTO {
  username: string;
  password: string;
}

export interface LoginResponseDTO {
  access: string;
  refresh: string;
  accessToken: string;
  refreshToken: string;
  user: AuthUserDTO;
  mustChangePassword: boolean;
}

export interface RefreshTokenRequestDTO {
  refresh: string;
}

export interface RefreshTokenResponseDTO {
  access: string;
  accessToken?: string;
}

export interface LogoutResponseDTO {
  ok: boolean;
  detail?: string;
}

export interface RolesResponseDTO {
  roles: Role[];
}

export function login(credentials: LoginRequestDTO, options?: Omit<RequestOptions, "body" | "method">) {
  return apiClient.post<LoginResponseDTO>("/api/auth/login/", credentials, options);
}

export function refreshAccessToken(refresh: string, options?: Omit<RequestOptions, "body" | "method">) {
  return apiClient.post<RefreshTokenResponseDTO>("/api/auth/refresh/", { refresh } satisfies RefreshTokenRequestDTO, options);
}

export function logout(accessToken: string, options?: Omit<RequestOptions, "body" | "method">) {
  return apiClient.post<LogoutResponseDTO>("/api/auth/logout/", undefined, { ...options, accessToken });
}

export function getCurrentUser(accessToken: string, options?: Omit<RequestOptions, "body" | "method">) {
  return apiClient.get<AuthUserDTO>("/api/auth/me/", { ...options, accessToken });
}

export function getRoles(accessToken: string, options?: Omit<RequestOptions, "body" | "method">) {
  return apiClient.get<RolesResponseDTO>("/api/auth/roles/", { ...options, accessToken });
}
