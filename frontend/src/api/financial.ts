import { request } from './client'
import type {
  FinancialAgentResult,
  FinancialCalculationCreatePayload,
  FinancialCalculationListResponse,
  FinancialCalculationRead,
  FinancialMetricCreatePayload,
  FinancialMetricListResponse,
  FinancialMetricRead,
  FinancialMetricUpdatePayload,
  RedFlagFindingCreatePayload,
  RedFlagFindingListResponse,
  RedFlagFindingRead,
  RedFlagFindingUpdatePayload,
  ResearchRequestPayload,
  ComparisonRequestPayload,
  ReportRequestPayload,
} from './types'

function enc(value: string): string {
  return encodeURIComponent(value)
}

export function listFinancialMetrics(
  workspaceId: string,
  params: { limit?: number; offset?: number; metric_type?: string; document_id?: string; red_flag_level?: string } = {},
  signal?: AbortSignal,
): Promise<FinancialMetricListResponse> {
  return request<FinancialMetricListResponse>(
    `/workspaces/${enc(workspaceId)}/financial-metrics`,
    {
      query: {
        limit: params.limit,
        offset: params.offset,
        metric_type: params.metric_type,
        document_id: params.document_id,
        red_flag_level: params.red_flag_level,
      },
      signal,
    },
  )
}

export function getFinancialMetric(id: string, signal?: AbortSignal): Promise<FinancialMetricRead> {
  return request<FinancialMetricRead>(`/financial-metrics/${enc(id)}`, { signal })
}

export function createFinancialMetric(
  workspaceId: string,
  payload: FinancialMetricCreatePayload,
  signal?: AbortSignal,
): Promise<FinancialMetricRead> {
  return request<FinancialMetricRead>(`/workspaces/${enc(workspaceId)}/financial-metrics`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function updateFinancialMetric(
  id: string,
  payload: FinancialMetricUpdatePayload,
  signal?: AbortSignal,
): Promise<FinancialMetricRead> {
  return request<FinancialMetricRead>(`/financial-metrics/${enc(id)}`, {
    method: 'PATCH',
    body: payload,
    signal,
  })
}

export function deleteFinancialMetric(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`/financial-metrics/${enc(id)}`, { method: 'DELETE', signal })
}

export function listFinancialCalculations(
  workspaceId: string,
  params: { limit?: number; offset?: number; calculation_type?: string } = {},
  signal?: AbortSignal,
): Promise<FinancialCalculationListResponse> {
  return request<FinancialCalculationListResponse>(
    `/workspaces/${enc(workspaceId)}/financial-calculations`,
    {
      query: {
        limit: params.limit,
        offset: params.offset,
        calculation_type: params.calculation_type,
      },
      signal,
    },
  )
}

export function getFinancialCalculation(id: string, signal?: AbortSignal): Promise<FinancialCalculationRead> {
  return request<FinancialCalculationRead>(`/financial-calculations/${enc(id)}`, { signal })
}

export function createFinancialCalculation(
  workspaceId: string,
  payload: FinancialCalculationCreatePayload,
  signal?: AbortSignal,
): Promise<FinancialCalculationRead> {
  return request<FinancialCalculationRead>(`/workspaces/${enc(workspaceId)}/financial-calculations`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function updateFinancialCalculation(
  id: string,
  payload: Partial<FinancialCalculationCreatePayload>,
  signal?: AbortSignal,
): Promise<FinancialCalculationRead> {
  return request<FinancialCalculationRead>(`/financial-calculations/${enc(id)}`, {
    method: 'PATCH',
    body: payload,
    signal,
  })
}

export function deleteFinancialCalculation(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`/financial-calculations/${enc(id)}`, { method: 'DELETE', signal })
}

export function listRedFlagFindings(
  workspaceId: string,
  params: { limit?: number; offset?: number; severity?: string; status?: string; document_id?: string } = {},
  signal?: AbortSignal,
): Promise<RedFlagFindingListResponse> {
  return request<RedFlagFindingListResponse>(`/workspaces/${enc(workspaceId)}/red-flags`, {
    query: {
      limit: params.limit,
      offset: params.offset,
      severity: params.severity,
      status: params.status,
      document_id: params.document_id,
    },
    signal,
  })
}

export function getRedFlagFinding(id: string, signal?: AbortSignal): Promise<RedFlagFindingRead> {
  return request<RedFlagFindingRead>(`/red-flags/${enc(id)}`, { signal })
}

export function createRedFlagFinding(
  workspaceId: string,
  payload: RedFlagFindingCreatePayload,
  signal?: AbortSignal,
): Promise<RedFlagFindingRead> {
  return request<RedFlagFindingRead>(`/workspaces/${enc(workspaceId)}/red-flags`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function updateRedFlagFinding(
  id: string,
  payload: RedFlagFindingUpdatePayload,
  signal?: AbortSignal,
): Promise<RedFlagFindingRead> {
  return request<RedFlagFindingRead>(`/red-flags/${enc(id)}`, {
    method: 'PATCH',
    body: payload,
    signal,
  })
}

export function deleteRedFlagFinding(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`/red-flags/${enc(id)}`, { method: 'DELETE', signal })
}

export function analyzeRedFlags(
  workspaceId: string,
  documentId?: string,
  signal?: AbortSignal,
): Promise<FinancialAgentResult> {
  return request<FinancialAgentResult>(`/workspaces/${enc(workspaceId)}/red-flags/analyze`, {
    method: 'POST',
    query: documentId ? { document_id: documentId } : undefined,
    signal,
  })
}

export function runResearch(
  workspaceId: string,
  payload: ResearchRequestPayload,
  signal?: AbortSignal,
): Promise<FinancialAgentResult> {
  return request<FinancialAgentResult>(`/workspaces/${enc(workspaceId)}/research`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function runComparison(
  workspaceId: string,
  payload: ComparisonRequestPayload,
  signal?: AbortSignal,
): Promise<FinancialAgentResult> {
  return request<FinancialAgentResult>(`/workspaces/${enc(workspaceId)}/compare`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function generateReport(
  workspaceId: string,
  payload: ReportRequestPayload,
  signal?: AbortSignal,
): Promise<FinancialAgentResult> {
  return request<FinancialAgentResult>(`/workspaces/${enc(workspaceId)}/reports`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function listCitations(
  workspaceId?: string,
  params: { limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<{ items: Array<Record<string, unknown>>; total: number; limit: number; offset: number }> {
  const path = workspaceId ? `/workspaces/${enc(workspaceId)}/citations` : '/citations'
  return request(path, {
    query: { limit: params.limit, offset: params.offset },
    signal,
  })
}

export function validateCitation(
  payload: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<{ valid: boolean; errors: string[] }> {
  return request<{ valid: boolean; errors: string[] }>('/citations/validate', {
    method: 'POST',
    body: payload,
    signal,
  })
}
