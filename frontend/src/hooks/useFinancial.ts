import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  analyzeRedFlags,
  createFinancialMetric,
  createRedFlagFinding,
  deleteFinancialMetric,
  deleteRedFlagFinding,
  generateReport,
  listFinancialCalculations,
  listFinancialMetrics,
  listRedFlagFindings,
  runComparison,
  runResearch,
  updateRedFlagFinding,
  validateCitation,
} from '../api/financial'
import type { FinancialAgentResult } from '../api/types'

export const financialKeys = {
  all: ['financial'] as const,
  metrics: (workspaceId: string, params: Record<string, unknown> = {}) =>
    ['financial', 'metrics', workspaceId, params] as const,
  calculations: (workspaceId: string, params: Record<string, unknown> = {}) =>
    ['financial', 'calculations', workspaceId, params] as const,
  redFlags: (workspaceId: string, params: Record<string, unknown> = {}) =>
    ['financial', 'red-flags', workspaceId, params] as const,
}

export function useFinancialMetrics(workspaceId: string | undefined, params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: financialKeys.metrics(workspaceId ?? '', params),
    queryFn: ({ signal }) => listFinancialMetrics(workspaceId as string, params as never, signal),
    enabled: Boolean(workspaceId),
    placeholderData: (previous) => previous,
  })
}

export function useFinancialCalculations(workspaceId: string | undefined, params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: financialKeys.calculations(workspaceId ?? '', params),
    queryFn: ({ signal }) => listFinancialCalculations(workspaceId as string, params as never, signal),
    enabled: Boolean(workspaceId),
    placeholderData: (previous) => previous,
  })
}

export function useRedFlagFindings(workspaceId: string | undefined, params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: financialKeys.redFlags(workspaceId ?? '', params),
    queryFn: ({ signal }) => listRedFlagFindings(workspaceId as string, params as never, signal),
    enabled: Boolean(workspaceId),
    placeholderData: (previous) => previous,
  })
}

export function useCreateFinancialMetric(workspaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof createFinancialMetric>[1]) =>
      createFinancialMetric(workspaceId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['financial', 'metrics', workspaceId] })
    },
  })
}

export function useCreateRedFlagFinding(workspaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof createRedFlagFinding>[1]) =>
      createRedFlagFinding(workspaceId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['financial', 'red-flags', workspaceId] })
    },
  })
}

export function useUpdateRedFlagFinding(workspaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateRedFlagFinding>[1] }) =>
      updateRedFlagFinding(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['financial', 'red-flags', workspaceId] })
    },
  })
}

export function useDeleteRedFlagFinding(workspaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteRedFlagFinding(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['financial', 'red-flags', workspaceId] })
    },
  })
}

export function useAnalyzeRedFlags(workspaceId: string) {
  const queryClient = useQueryClient()
  return useMutation<FinancialAgentResult, unknown, { documentId?: string }>({
    mutationFn: ({ documentId }) => analyzeRedFlags(workspaceId, documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['financial', 'red-flags', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['financial', 'metrics', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['financial', 'calculations', workspaceId] })
    },
  })
}

export function useResearch(workspaceId: string) {
  return useMutation<FinancialAgentResult, unknown, Parameters<typeof runResearch>[1]>({
    mutationFn: (payload) => runResearch(workspaceId, payload),
  })
}

export function useComparison(workspaceId: string) {
  return useMutation<FinancialAgentResult, unknown, Parameters<typeof runComparison>[1]>({
    mutationFn: (payload) => runComparison(workspaceId, payload),
  })
}

export function useGenerateReport(workspaceId: string) {
  return useMutation<FinancialAgentResult, unknown, Parameters<typeof generateReport>[1]>({
    mutationFn: (payload) => generateReport(workspaceId, payload),
  })
}

export function useValidateCitation() {
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => validateCitation(payload),
  })
}

export { deleteFinancialMetric }
