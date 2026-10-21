import { useMutation } from '@tanstack/react-query'
import { searchWorkspace } from '../api/search'
import type { SearchRequestPayload, SearchResponse } from '../api/types'

export function useWorkspaceSearch(workspaceId: string | undefined) {
  return useMutation({
    mutationFn: (payload: SearchRequestPayload): Promise<SearchResponse> =>
      searchWorkspace(workspaceId as string, payload),
  })
}
