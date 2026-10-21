import { request, uploadFile } from './client'
import type { UploadOptions } from './client'
import type {
  DocumentListResponse,
  DocumentRead,
  DocumentRetryResponse,
  DocumentUploadResponse,
} from './types'

export interface DocumentListParams {
  limit?: number
  offset?: number
  status?: string
  document_type?: string
  company_name?: string
}

export interface DocumentUploadInput {
  file: File
  company_name?: string
  document_title?: string
  document_type?: string
  fiscal_period?: string
  source_url?: string
}

export function listDocuments(
  workspaceId: string,
  params: DocumentListParams = {},
  signal?: AbortSignal,
): Promise<DocumentListResponse> {
  return request<DocumentListResponse>(
    `/workspaces/${encodeURIComponent(workspaceId)}/documents`,
    {
      query: {
        limit: params.limit,
        offset: params.offset,
        status: params.status,
        document_type: params.document_type,
        company_name: params.company_name,
      },
      signal,
    },
  )
}

export function getDocument(id: string, signal?: AbortSignal): Promise<DocumentRead> {
  return request<DocumentRead>(`/documents/${encodeURIComponent(id)}`, { signal })
}

export function uploadDocument(
  workspaceId: string,
  input: DocumentUploadInput,
  options: UploadOptions = {},
): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', input.file, input.file.name)
  if (input.company_name) formData.append('company_name', input.company_name)
  if (input.document_title) formData.append('document_title', input.document_title)
  if (input.document_type) formData.append('document_type', input.document_type)
  if (input.fiscal_period) formData.append('fiscal_period', input.fiscal_period)
  if (input.source_url) formData.append('source_url', input.source_url)

  return uploadFile<DocumentUploadResponse>(
    `/workspaces/${encodeURIComponent(workspaceId)}/documents`,
    formData,
    options,
  )
}

export function retryDocument(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentRetryResponse> {
  return request<DocumentRetryResponse>(`/documents/${encodeURIComponent(documentId)}/retry`, {
    method: 'POST',
    signal,
  })
}

export function deleteDocument(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`/documents/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    signal,
  })
}
