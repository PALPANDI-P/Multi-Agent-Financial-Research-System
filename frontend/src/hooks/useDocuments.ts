import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteDocument,
  listDocuments,
  retryDocument,
  uploadDocument,
} from '../api/documents'
import type { DocumentListParams, DocumentUploadInput } from '../api/documents'
import { workspaceKeys } from './useWorkspaces'

export const documentKeys = {
  all: ['documents'] as const,
  lists: () => ['documents', 'list'] as const,
  list: (workspaceId: string, params: DocumentListParams) =>
    ['documents', 'list', workspaceId, params] as const,
  detail: (id: string) => ['documents', 'detail', id] as const,
}

export function useDocuments(workspaceId: string | undefined, params: DocumentListParams) {
  return useQuery({
    queryKey: documentKeys.list(workspaceId ?? '', params),
    queryFn: ({ signal }) => listDocuments(workspaceId as string, params, signal),
    enabled: Boolean(workspaceId),
    placeholderData: (previous) => previous,
  })
}

export function useUploadDocument(workspaceId: string) {
  const queryClient = useQueryClient()
  const [progress, setProgress] = useState<number | null>(null)

  const mutation = useMutation({
    mutationFn: (input: DocumentUploadInput) => {
      setProgress(0)
      return uploadDocument(workspaceId, input, {
        onProgress: (percent) => setProgress(percent),
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.detail(workspaceId) })
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.lists() })
    },
  })

  return { ...mutation, progress }
}

export function useRetryDocument(workspaceId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (documentId: string) => retryDocument(documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.detail(workspaceId) })
    },
  })
}

export function useDeleteDocument(workspaceId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.detail(workspaceId) })
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.lists() })
    },
  })
}
