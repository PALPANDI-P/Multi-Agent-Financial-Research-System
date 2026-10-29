/**
 * TypeScript mirrors of the backend API contract.
 * Field names and nullability match the FastAPI pydantic schemas exactly.
 */

export interface WorkspaceRead {
  id: string
  name: string
  description: string | null
  owner_id: string | null
  document_count: number
  created_at: string
  updated_at: string
}

export interface WorkspaceListResponse {
  items: WorkspaceRead[]
  total: number
  limit: number
  offset: number
}

export interface WorkspaceCreatePayload {
  name: string
  description?: string
}

export interface WorkspaceUpdatePayload {
  name?: string
  description?: string
}

export interface DocumentRead {
  id: string
  workspace_id: string
  original_filename: string
  content_hash: string
  file_size_bytes: number
  mime_type: string
  company_name: string | null
  document_title: string | null
  document_type: string | null
  fiscal_period: string | null
  source_url: string | null
  page_count: number | null
  processing_status: string
  processing_stage: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  processed_at: string | null
  chunk_count: number
}

export interface DocumentListResponse {
  items: DocumentRead[]
  total: number
  limit: number
  offset: number
}

export interface DocumentUploadResponse {
  document_id: string
  processing_status: string
  processing_stage: string | null
  content_hash: string
  duplicate: boolean
}

export interface DocumentRetryResponse {
  document_id: string
  job_id: string
  attempt_count: number
  processing_status: string
}

export interface SearchRequestPayload {
  query: string
  limit?: number
  document_ids?: string[]
  chunk_types?: string[]
}

export interface SearchResultItem {
  chunk_id: string
  document_id: string
  document_title: string | null
  company_name: string | null
  document_type: string | null
  fiscal_period: string | null
  page_start: number | null
  page_end: number | null
  section_heading: string | null
  chunk_type: string
  content: string
  score: number
  metadata: Record<string, unknown>
}

export interface SearchResponse {
  query: string
  workspace_id: string | null
  total: number
  results: SearchResultItem[]
  took_ms: number
}

export interface HealthResponse {
  status: string
  app: string
  version: string
  environment: string
  timestamp: string
  checks: Record<string, string>
}

export interface ApiErrorBody {
  code: string
  message: string
  details?: unknown
  request_id?: string
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody
}

/** Processing status values emitted by the backend ingestion pipeline. */
export const PROCESSING_STATUSES = [
  'queued',
  'validating',
  'extracting',
  'chunking',
  'embedding',
  'indexing',
  'completed',
  'failed',
] as const

export type ProcessingStatus = (typeof PROCESSING_STATUSES)[number]

/* ---------------------------------------------------------------------------
 * Authentication
 *
 * Mirrors of the frozen `/api/v1/auth` contract of the backend.
 * ------------------------------------------------------------------------- */

export type UserRole = 'analyst' | 'researcher' | 'administrator'

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: UserRole
  scenario_key: string | null
  created_at?: string
  last_login_at?: string | null
}

export interface LoginResponse {
  user: AuthUser
  expires_at: string
}

export interface AuthScenario {
  key: string
  title: string
  tagline: string
  description: string
  focus_areas: string[]
  suggested_queries: string[]
  demo_email: string | null
  demo_password: string | null
}

export interface AuthScenariosResponse {
  scenarios: AuthScenario[]
}

export interface RegisterPayload {
  email: string
  full_name: string
  password: string
}

/** The registration endpoint answers with the created user. */
export type RegisterResponse = AuthUser

/* ---------------------------------------------------------------------------
 * Financial analysis
 * Mirrors of the backend /api/v1 financial contract.
 * ------------------------------------------------------------------------- */

export interface FinancialMetricRead {
  id: string
  workspace_id: string
  document_id: string
  metric_type: string
  metric_name: string
  metric_value: unknown
  currency: string | null
  unit: string | null
  red_flag_level: string | null
  calculation_id: string | null
  context: Record<string, unknown> | null
  source_document_chunk: string | null
  extracted_at: string | null
  is_estimated: boolean
  is_projected: boolean
  notes: string | null
  created_at: string | null
  updated_at: string | null
}

export interface FinancialMetricListResponse {
  items: FinancialMetricRead[]
  total: number
  limit: number
  offset: number
}

export interface FinancialMetricCreatePayload {
  workspace_id?: string
  document_id: string
  metric_type: string
  metric_name: string
  metric_value: string | number
  currency?: string | null
  unit?: string | null
  red_flag_level?: string | null
  calculation_id?: string | null
  context?: Record<string, unknown> | null
  source_document_chunk?: string | null
  extracted_at?: string | null
  is_estimated?: boolean
  is_projected?: boolean
  notes?: string | null
}

export interface FinancialMetricUpdatePayload {
  metric_type?: string | null
  metric_name?: string | null
  metric_value?: string | number | null
  currency?: string | null
  unit?: string | null
  red_flag_level?: string | null
  calculation_id?: string | null
  context?: Record<string, unknown> | null
  source_document_chunk?: string | null
  is_estimated?: boolean | null
  is_projected?: boolean | null
  notes?: string | null
}

export interface FinancialCalculationRead {
  id: string
  workspace_id: string
  calculation_type: string
  calculation_name: string
  formula: string | null
  result_value: unknown
  currency: string | null
  unit: string | null
  parent_calculation_id: string | null
  description: string | null
  calculation_metadata: Record<string, unknown> | null
  input_metrics: Array<Record<string, unknown>> | null
  execution_context: Record<string, unknown> | null
  calculated_at: string | null
  confidence_score: unknown
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export interface FinancialCalculationListResponse {
  items: FinancialCalculationRead[]
  total: number
  limit: number
  offset: number
}

export interface FinancialCalculationCreatePayload {
  workspace_id?: string
  calculation_type: string
  calculation_name: string
  formula?: string | null
  result_value: string | number
  currency?: string | null
  unit?: string | null
  parent_calculation_id?: string | null
  description?: string | null
  calculation_metadata?: Record<string, unknown> | null
  input_metrics?: Array<Record<string, unknown>> | null
  execution_context?: Record<string, unknown> | null
  calculated_at?: string | null
  confidence_score?: string | number | null
  error_message?: string | null
}

export interface RedFlagFindingRead {
  id: string
  workspace_id: string
  document_id: string | null
  financial_metric_id: string | null
  financial_calculation_id: string | null
  agent_run_id: string | null
  flag_type: string
  severity: string
  title: string | null
  description: string | null
  evidence: Record<string, unknown> | null
  source_excerpt: string | null
  confidence_score: unknown
  status: string
  detected_by: string | null
  detected_at: string | null
  resolved_at: string | null
  resolution_notes: string | null
  finding_metadata: Record<string, unknown> | null
  created_at: string | null
  updated_at: string | null
}

export interface RedFlagFindingListResponse {
  items: RedFlagFindingRead[]
  total: number
  limit: number
  offset: number
}

export interface RedFlagFindingCreatePayload {
  workspace_id?: string
  document_id?: string | null
  financial_metric_id?: string | null
  financial_calculation_id?: string | null
  agent_run_id?: string | null
  flag_type: string
  severity?: string
  title?: string | null
  description?: string | null
  evidence?: Record<string, unknown> | null
  source_excerpt?: string | null
  confidence_score?: string | number | null
  status?: string
  detected_by?: string | null
  resolution_notes?: string | null
  finding_metadata?: Record<string, unknown> | null
}

export interface RedFlagFindingUpdatePayload {
  severity?: string | null
  title?: string | null
  description?: string | null
  evidence?: Record<string, unknown> | null
  source_excerpt?: string | null
  confidence_score?: string | number | null
  status?: string | null
  resolution_notes?: string | null
  finding_metadata?: Record<string, unknown> | null
}

export interface ResearchRequestPayload {
  question?: string
  query?: string
  text?: string
  prompt?: string
  document_id?: string
  document_ids?: string[]
  top_k?: number
  limit?: number
}

export interface ComparisonRequestPayload {
  question?: string
  query?: string
  company_a?: string
  company_b?: string
  document_ids?: string[]
  metric_names?: string[]
  top_k?: number
  limit?: number
}

export interface ReportRequestPayload {
  title?: string
  question?: string
  query?: string
  document_ids?: string[]
  include_metrics?: boolean
  include_red_flags?: boolean
  top_k?: number
  limit?: number
}

export type FinancialAgentResult = Record<string, unknown>

