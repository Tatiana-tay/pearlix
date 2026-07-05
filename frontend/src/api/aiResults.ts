import { apiClient } from "./client";
import type { RequestOptions } from "./types";
import type { BackendAIResult, BackendAIResultFinding } from "../types/models";

export type AIResultStatus = "Pending" | "Processing" | "Completed" | "Failed";

export interface AIResultFindingDTO {
  id: number | string;
  toothFdi: string;
  diseaseLabel: string;
  confidence: number;
  bbox?: unknown;
  mask?: unknown;
  metadata?: Record<string, unknown>;
  createdAt?: string;
}

export interface AIResultDTO {
  id: number | string;
  attachmentId: number | string;
  patientId?: number | string;
  patientName?: string;
  visitId?: number | string | null;
  status: AIResultStatus;
  resultSummary?: string;
  modelName: string;
  modelVersion: string;
  overallConfidence?: number | null;
  overlayUrl?: string;
  errorMessage?: string;
  metadata?: Record<string, unknown>;
  findings?: AIResultFindingDTO[];
  createdById?: number | string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface AIResultListQuery {
  attachmentId?: string | number;
  patientId?: string | number;
  visitId?: string | number;
  status?: AIResultStatus;
  modelVersion?: string;
  from?: string;
  to?: string;
}

interface AIResultListResponse {
  results: AIResultDTO[];
}

type AuthenticatedOptions = Omit<RequestOptions, "body" | "method" | "query"> & {
  accessToken: string;
};

export async function listAIResults(query: AIResultListQuery, options: AuthenticatedOptions) {
  const response = await apiClient.get<AIResultDTO[] | AIResultListResponse>("/api/ai-results/", {
    ...options,
    query: { ...query },
  });
  return Array.isArray(response) ? response : response.results;
}

export function getAIResult(aiResultId: string | number, options: AuthenticatedOptions) {
  return apiClient.get<AIResultDTO>(`/api/ai-results/${aiResultId}/`, options);
}

export async function listAttachmentAIResults(attachmentId: string | number, options: AuthenticatedOptions) {
  const response = await apiClient.get<AIResultDTO[] | AIResultListResponse>(`/api/attachments/${attachmentId}/ai-results/`, options);
  return Array.isArray(response) ? response : response.results;
}

export function getLatestAttachmentAIResult(attachmentId: string | number, options: AuthenticatedOptions) {
  return apiClient.get<AIResultDTO>(`/api/attachments/${attachmentId}/ai-result/`, options);
}

export async function listAIResultFindings(aiResultId: string | number, options: AuthenticatedOptions) {
  const response = await apiClient.get<AIResultFindingDTO[] | { results: AIResultFindingDTO[] }>(`/api/ai-results/${aiResultId}/findings/`, options);
  return Array.isArray(response) ? response : response.results;
}

export function adaptAIResultDTO(result: AIResultDTO): BackendAIResult {
  const analysisId = String(result.id);
  return {
    analysisId,
    fileId: String(result.attachmentId),
    attachmentId: String(result.attachmentId),
    patientId: result.patientId === undefined ? undefined : String(result.patientId),
    patientName: result.patientName ?? "",
    visitId: result.visitId === null || result.visitId === undefined ? undefined : String(result.visitId),
    resultSummary: result.resultSummary ?? "",
    overallConfidence: result.overallConfidence ?? 0,
    processedDate: result.updatedAt ?? result.createdAt ?? "",
    modelName: result.modelName,
    modelVersion: result.modelVersion,
    status: result.status,
    overlayFilePath: "",
    overlayUrl: "",
    errorMessage: result.errorMessage ?? "",
    findings: (result.findings ?? []).map((finding) => ({
      ...adaptAIResultFindingDTO(finding),
      analysisId,
    })),
    createdAt: result.createdAt,
    updatedAt: result.updatedAt,
  };
}

export function adaptAIResultFindingDTO(finding: AIResultFindingDTO): BackendAIResultFinding {
  return {
    findingId: String(finding.id),
    analysisId: "",
    fdiToothId: finding.toothFdi,
    diseaseLabel: finding.diseaseLabel,
    confidenceScore: finding.confidence,
    createdAt: finding.createdAt,
  };
}
