import type { ApiValidationErrors } from "./types";

const statusMessages: Record<number, string> = {
  400: "Validation error.",
  401: "Authentication is required.",
  403: "You do not have permission to perform this action.",
  404: "The requested resource was not found.",
  409: "This record was updated by someone else. Please refresh and try again.",
  500: "The server returned an error.",
};

interface ApiErrorParams {
  status: number;
  message: string;
  rawBody?: unknown;
  currentVersion?: number;
  validationErrors?: ApiValidationErrors;
}

export class ApiError extends Error {
  readonly status: number;
  readonly details?: unknown;
  readonly rawBody?: unknown;
  readonly currentVersion?: number;
  readonly validationErrors?: ApiValidationErrors;

  constructor({ status, message, rawBody, currentVersion, validationErrors }: ApiErrorParams) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = rawBody;
    this.rawBody = rawBody;
    this.currentVersion = currentVersion;
    this.validationErrors = validationErrors;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export function createApiError(status: number, rawBody: unknown): ApiError {
  return new ApiError({
    status,
    message: extractMessage(rawBody) ?? statusMessages[status] ?? `Request failed with status ${status}.`,
    rawBody,
    currentVersion: extractCurrentVersion(rawBody),
    validationErrors: extractValidationErrors(rawBody),
  });
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function extractMessage(rawBody: unknown): string | undefined {
  const directMessage = normalizeMessage(rawBody);
  if (directMessage) {
    return directMessage;
  }

  if (!isRecord(rawBody)) {
    return undefined;
  }

  return (
    normalizeMessage(rawBody.detail) ??
    normalizeMessage(rawBody.message) ??
    normalizeMessage(rawBody.error) ??
    normalizeMessage(rawBody.nonFieldErrors) ??
    normalizeMessage(rawBody.non_field_errors) ??
    firstValidationMessage(rawBody.errors) ??
    firstValidationMessage(rawBody)
  );
}

function normalizeMessage(value: unknown): string | undefined {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed || undefined;
  }

  if (Array.isArray(value)) {
    const message = value
      .map((item) => normalizeMessage(item))
      .filter((item): item is string => Boolean(item))
      .join(" ");
    return message || undefined;
  }

  return undefined;
}

function extractCurrentVersion(rawBody: unknown): number | undefined {
  if (!isRecord(rawBody)) {
    return undefined;
  }

  const value = rawBody.currentVersion ?? rawBody.current_version;
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : undefined;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function extractValidationErrors(rawBody: unknown): ApiValidationErrors | undefined {
  if (!isRecord(rawBody)) {
    return undefined;
  }

  const source = isRecord(rawBody.errors) ? rawBody.errors : rawBody;
  const errors: ApiValidationErrors = {};
  const ignoredKeys = new Set([
    "currentVersion",
    "current_version",
    "detail",
    "error",
    "message",
    "nonFieldErrors",
    "non_field_errors",
  ]);

  Object.entries(source).forEach(([key, value]) => {
    if (ignoredKeys.has(key)) {
      return;
    }

    const messages = collectValidationMessages(value);
    if (messages.length > 0) {
      errors[key] = messages;
    }
  });

  return Object.keys(errors).length > 0 ? errors : undefined;
}

function firstValidationMessage(value: unknown): string | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  for (const item of Object.values(value)) {
    const message = collectValidationMessages(item)[0];
    if (message) {
      return message;
    }
  }

  return undefined;
}

function collectValidationMessages(value: unknown): string[] {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : [];
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => collectValidationMessages(item));
  }

  if (isRecord(value)) {
    return Object.entries(value).flatMap(([key, nestedValue]) =>
      collectValidationMessages(nestedValue).map((message) => `${key}: ${message}`),
    );
  }

  return [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
