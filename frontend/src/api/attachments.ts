import { apiBaseUrl, apiClient } from "./client";
import { createApiError } from "./errors";
import type { RequestOptions } from "./types";
import type { BackendAttachment } from "../types/models";

export type AttachmentType = "X-ray" | "Document" | "Other";

export interface AttachmentDTO {
  id: number | string;
  patientId: number | string;
  patientName?: string;
  visitId?: number | string | null;
  uploadedById?: number | string | null;
  uploadedByName?: string | null;
  attachmentType: AttachmentType;
  originalFilename: string;
  contentType: string;
  sizeBytes: number;
  fileUrl?: string | null;
  description?: string;
  isDeleted?: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface AttachmentListQuery {
  patientId?: string | number;
  visitId?: string | number;
  attachmentType?: AttachmentType;
  uploadedById?: string | number;
  from?: string;
  to?: string;
}

export interface AttachmentUploadPayload {
  patientId: string | number;
  visitId?: string | number | null;
  file: File;
  attachmentType?: AttachmentType;
  description?: string;
}

interface AttachmentListResponse {
  results: AttachmentDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method" | "query"> & {
  accessToken: string;
};

export async function listAttachments(query: AttachmentListQuery, options: AuthenticatedOptions) {
  const response = await apiClient.get<AttachmentDTO[] | AttachmentListResponse>("/api/attachments/", {
    ...options,
    query: { ...query },
  });
  return Array.isArray(response) ? response : response.results;
}

export async function listVisitAttachments(visitId: string | number, options: AuthenticatedOptions) {
  const response = await apiClient.get<AttachmentDTO[] | AttachmentListResponse>(`/api/visits/${visitId}/attachments/`, options);
  return Array.isArray(response) ? response : response.results;
}

export function getAttachment(attachmentId: string | number, options: AuthenticatedOptions) {
  return apiClient.get<AttachmentDTO>(`/api/attachments/${attachmentId}/`, options);
}

export function uploadAttachment(payload: AttachmentUploadPayload, options: AuthenticatedOptions) {
  const formData = toAttachmentFormData(payload);
  return apiClient.post<AttachmentDTO>("/api/attachments/", formData, options);
}

export function uploadVisitAttachment(visitId: string | number, payload: AttachmentUploadPayload, options: AuthenticatedOptions) {
  const formData = toAttachmentFormData(payload);
  return apiClient.post<AttachmentDTO>(`/api/visits/${visitId}/attachments/`, formData, options);
}

export function updateAttachmentDescription(attachmentId: string | number, description: string, options: AuthenticatedOptions) {
  return apiClient.patch<AttachmentDTO>(`/api/attachments/${attachmentId}/`, { description }, options);
}

export function deleteAttachment(attachmentId: string | number, options: AuthenticatedOptions) {
  return apiClient.delete<void>(`/api/attachments/${attachmentId}/`, options);
}

export async function fetchAttachmentOriginalBlob(attachmentId: string | number, options: AuthenticatedOptions) {
  const response = await fetch(`${apiBaseUrl}/api/attachments/${attachmentId}/original-url/`, {
    headers: {
      Accept: "*/*",
      Authorization: `Bearer ${options.accessToken}`,
    },
  });

  if (!response.ok) {
    let body: unknown = undefined;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    throw createApiError(response.status, body);
  }

  return response.blob();
}

export function toAttachmentFormData(payload: AttachmentUploadPayload) {
  const formData = new FormData();
  formData.append("patientId", String(payload.patientId));
  if (payload.visitId !== undefined && payload.visitId !== null && payload.visitId !== "") {
    formData.append("visitId", String(payload.visitId));
  }
  if (payload.attachmentType) {
    formData.append("attachmentType", payload.attachmentType);
  }
  if (payload.description) {
    formData.append("description", payload.description);
  }
  formData.append("file", payload.file);
  return formData;
}

export function adaptAttachmentDTO(attachment: AttachmentDTO): BackendAttachment {
  return {
    id: String(attachment.id),
    patientId: String(attachment.patientId),
    patientName: attachment.patientName ?? "",
    visitId: attachment.visitId === null || attachment.visitId === undefined ? "" : String(attachment.visitId),
    uploadedById: attachment.uploadedById === null || attachment.uploadedById === undefined ? "" : String(attachment.uploadedById),
    uploadedByName: attachment.uploadedByName ?? "",
    filePath: "",
    fileName: attachment.originalFilename,
    fileType: attachment.attachmentType,
    mimeType: attachment.contentType,
    fileSize: attachment.sizeBytes,
    fileUrl: attachment.fileUrl ?? "",
    description: attachment.description ?? "",
    uploadedBy: attachment.uploadedByName ?? (attachment.uploadedById === null || attachment.uploadedById === undefined ? "" : String(attachment.uploadedById)),
    uploadedAt: attachment.createdAt ?? "",
    createdAt: attachment.createdAt,
    updatedAt: attachment.updatedAt,
  };
}
