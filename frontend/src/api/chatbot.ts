import { request } from './client'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface SourceChunk {
  chunk_id: string
  document_id: string
  document_title: string | null
  company_name: string | null
  document_type: string | null
  fiscal_period: string | null
  page_start: number | null
  page_end: number | null
  section_heading: string | null
  content: string
  score: number
}

export interface ChatResponse {
  message_id: string
  answer: string
  sources: SourceChunk[]
  took_ms: number
  document_count: number
  source_count: number
}

export interface ChatRequestPayload {
  question: string
  history?: ChatMessage[]
  document_ids?: string[]
  top_k?: number
}

export function sendChatMessage(
  workspaceId: string,
  payload: ChatRequestPayload,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return request<ChatResponse>(`/workspaces/${encodeURIComponent(workspaceId)}/chat`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

