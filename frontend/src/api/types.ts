export type Role = "Admin" | "Staff" | "Doctor";

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

export type ApiValidationErrors = Record<string, string[]>;

export interface ApiErrorResponse {
  detail?: string | string[] | ApiValidationErrors;
  message?: string;
  error?: string;
  errors?: ApiValidationErrors | Record<string, unknown>;
  currentVersion?: number | string;
  current_version?: number | string;
  [key: string]: unknown;
}

export type QueryParamValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryParamValue | QueryParamValue[]>;

export interface RequestOptions extends Omit<RequestInit, "body" | "headers" | "method"> {
  accessToken?: string | null;
  body?: unknown;
  headers?: HeadersInit;
  method?: HttpMethod;
  query?: QueryParams;
}

export interface ApiClientConfig {
  baseUrl?: string;
  getAccessToken?: () => string | null | undefined;
}
