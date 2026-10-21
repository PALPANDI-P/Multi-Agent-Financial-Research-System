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
