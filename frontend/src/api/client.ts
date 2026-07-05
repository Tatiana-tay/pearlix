import { createApiError } from "./errors";
import type { ApiClientConfig, QueryParamValue, QueryParams, RequestOptions } from "./types";

const defaultApiBaseUrl = "http://127.0.0.1:8000";

export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL?.trim() || defaultApiBaseUrl).replace(/\/+$/, "");

export class ApiClient {
  private readonly baseUrl: string;
  private readonly getAccessToken?: () => string | null | undefined;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = (config.baseUrl?.trim() || apiBaseUrl).replace(/\/+$/, "");
    this.getAccessToken = config.getAccessToken;
  }

  async request<TResponse = unknown>(path: string, options: RequestOptions = {}): Promise<TResponse> {
    const { accessToken, body, headers: requestHeaders, method = "GET", query, ...fetchOptions } = options;
    const headers = new Headers(requestHeaders);
    const token = accessToken ?? this.getAccessToken?.();

    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(buildUrl(this.baseUrl, path, query), {
      ...fetchOptions,
      body: prepareBody(body, headers),
      headers,
      method,
    });
    const parsedBody = await parseResponseBody(response);

    if (!response.ok) {
      throw createApiError(response.status, parsedBody);
    }

    return parsedBody as TResponse;
  }

  get<TResponse = unknown>(path: string, options: Omit<RequestOptions, "body" | "method"> = {}) {
    return this.request<TResponse>(path, { ...options, method: "GET" });
  }

  post<TResponse = unknown>(path: string, body?: unknown, options: Omit<RequestOptions, "body" | "method"> = {}) {
    return this.request<TResponse>(path, { ...options, body, method: "POST" });
  }

  patch<TResponse = unknown>(path: string, body?: unknown, options: Omit<RequestOptions, "body" | "method"> = {}) {
    return this.request<TResponse>(path, { ...options, body, method: "PATCH" });
  }

  delete<TResponse = unknown>(path: string, options: Omit<RequestOptions, "method"> = {}) {
    return this.request<TResponse>(path, { ...options, method: "DELETE" });
  }
}

export const apiClient = new ApiClient();

function buildUrl(baseUrl: string, path: string, query?: QueryParams) {
  const isAbsoluteUrl = /^https?:\/\//i.test(path);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(isAbsoluteUrl ? path : `${baseUrl}${normalizedPath}`);

  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => appendQueryParam(url, key, item));
      return;
    }
    appendQueryParam(url, key, value);
  });

  return url.toString();
}

function appendQueryParam(url: URL, key: string, value: QueryParamValue) {
  if (value === null || value === undefined) {
    return;
  }
  url.searchParams.append(key, String(value));
}

function prepareBody(body: unknown, headers: Headers): BodyInit | undefined {
  if (body === undefined || body === null) {
    return undefined;
  }

  if (isBodyInit(body)) {
    return body;
  }

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return JSON.stringify(body);
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }

  const text = await response.text();
  if (!text) {
    return undefined;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function isBodyInit(value: unknown): value is BodyInit {
  return (
    typeof value === "string" ||
    isBlob(value) ||
    isFormData(value) ||
    isReadableStream(value) ||
    isUrlSearchParams(value) ||
    value instanceof ArrayBuffer ||
    ArrayBuffer.isView(value)
  );
}

function isBlob(value: unknown): value is Blob {
  return typeof Blob !== "undefined" && value instanceof Blob;
}

function isFormData(value: unknown): value is FormData {
  return typeof FormData !== "undefined" && value instanceof FormData;
}

function isReadableStream(value: unknown): value is ReadableStream {
  return typeof ReadableStream !== "undefined" && value instanceof ReadableStream;
}

function isUrlSearchParams(value: unknown): value is URLSearchParams {
  return typeof URLSearchParams !== "undefined" && value instanceof URLSearchParams;
}
