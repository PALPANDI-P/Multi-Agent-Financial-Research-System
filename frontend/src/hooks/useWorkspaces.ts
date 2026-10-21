import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createWorkspace,
  deleteWorkspace,
  getWorkspace,
  listWorkspaces,
  updateWorkspace,
} from '../api/workspaces'
import type { WorkspaceListParams } from '../api/workspaces'
import type {
  WorkspaceCreatePayload,
  WorkspaceListResponse,
  WorkspaceRead,
  WorkspaceUpdatePayload,
} from '../api/types'

export const workspaceKeys = {
  all: ['workspaces'] as const,
  lists: () => ['workspaces', 'list'] as const,
  list: (params: WorkspaceListParams) => ['workspaces', 'list', params] as const,
  detail: (id: string) => ['workspaces', 'detail', id] as const,
}

export function useWorkspaces(params: WorkspaceListParams) {
  return useQuery({
    queryKey: workspaceKeys.list(params),
    queryFn: ({ signal }) => listWorkspaces(params, signal),
    placeholderData: (previous) => previous,
  })
}

export function useWorkspace(id: string | undefined) {
  return useQuery({
    queryKey: workspaceKeys.detail(id ?? ''),
    queryFn: ({ signal }) => getWorkspace(id as string, signal),
    enabled: Boolean(id),
    retry: false,
  })
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: WorkspaceCreatePayload) => createWorkspace(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.lists() })
    },
  })
}

export function useUpdateWorkspace() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string
      payload: WorkspaceUpdatePayload
    }) => updateWorkspace(id, payload),
    onSuccess: (updated: WorkspaceRead) => {
      queryClient.setQueryData(workspaceKeys.detail(updated.id), updated)
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.lists() })
    },
  })
}

export function useDeleteWorkspace() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => deleteWorkspace(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: workspaceKeys.detail(id) })
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.lists() })
    },
  })
}

export type WorkspacesQuery = ReturnType<typeof useWorkspaces>
export type WorkspacesResponse = WorkspaceListResponse
