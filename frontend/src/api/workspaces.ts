import { request } from './client'
import type {
  WorkspaceCreatePayload,
  WorkspaceListResponse,
  WorkspaceRead,
  WorkspaceUpdatePayload,
} from './types'

export interface WorkspaceListParams {
  limit?: number
  offset?: number
  name?: string
}

export function listWorkspaces(
  params: WorkspaceListParams = {},
  signal?: AbortSignal,
): Promise<WorkspaceListResponse> {
  return request<WorkspaceListResponse>('/workspaces', {
    query: {
      limit: params.limit,
      offset: params.offset,
      name: params.name,
    },
    signal,
  })
}

export function getWorkspace(id: string, signal?: AbortSignal): Promise<WorkspaceRead> {
  return request<WorkspaceRead>(`/workspaces/${encodeURIComponent(id)}`, { signal })
}

export function createWorkspace(
  payload: WorkspaceCreatePayload,
  signal?: AbortSignal,
): Promise<WorkspaceRead> {
  return request<WorkspaceRead>('/workspaces', {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function updateWorkspace(
  id: string,
  payload: WorkspaceUpdatePayload,
  signal?: AbortSignal,
): Promise<WorkspaceRead> {
  return request<WorkspaceRead>(`/workspaces/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: payload,
    signal,
  })
}

export function deleteWorkspace(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`/workspaces/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    signal,
  })
}
