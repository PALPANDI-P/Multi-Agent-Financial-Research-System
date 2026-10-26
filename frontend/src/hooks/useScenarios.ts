import { useQuery } from '@tanstack/react-query'
import { fetchScenarios } from '../api/auth'
import type { AuthScenario } from '../api/types'

export const scenarioKeys = {
  all: ['auth', 'scenarios'] as const,
}

/**
 * The analyst scenarios of the product.  They are read from the API - the
 * frontend never hard codes them.
 */
export function useScenarios() {
  return useQuery<AuthScenario[]>({
    queryKey: scenarioKeys.all,
    queryFn: ({ signal }) => fetchScenarios(signal),
    staleTime: 5 * 60_000,
    retry: false,
  })
}