import { request } from './client'
import type { SearchRequestPayload, SearchResponse } from './types'

export function searchWorkspace(
  workspaceId: string,
  payload: SearchRequestPayload,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  return request<SearchResponse>(`/workspaces/${encodeURIComponent(workspaceId)}/search`, {
    method: 'POST',
    body: payload,
    signal,
  })
}
