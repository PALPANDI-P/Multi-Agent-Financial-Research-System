import { useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import { Alert, Button, Card, CardBody, CardHeader, EmptyState, Input, SkeletonText } from '../../components'
import { useComparison } from '../../hooks/useFinancial'
import type { FinancialAgentResult } from '../../api/types'

export interface ComparisonInterfaceProps {
  workspaceId: string
}

function pickText(result: FinancialAgentResult | undefined): string {
  if (!result) return ''
  const candidates = ['answer', 'summary', 'comparison', 'analysis', 'text', 'response']
  for (const key of candidates) {
    const value = result[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return ''
}

function pickCitations(result: FinancialAgentResult | undefined): Array<Record<string, unknown>> {
  if (!result) return []
  const candidates = ['citations', 'source_citations', 'sources', 'references', 'evidence']
  for (const key of candidates) {
    const value = result[key]
    if (Array.isArray(value)) return value as Array<Record<string, unknown>>
  }
  return []
}

export function ComparisonInterface({ workspaceId }: ComparisonInterfaceProps) {
  const [question, setQuestion] = useState('')
  const [companyA, setCompanyA] = useState('')
  const [companyB, setCompanyB] = useState('')
  const comparison = useComparison(workspaceId)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await comparison.mutateAsync({
        ...(question.trim() ? { question: question.trim() } : {}),
        ...(companyA.trim() ? { company_a: companyA.trim() } : {}),
        ...(companyB.trim() ? { company_b: companyB.trim() } : {}),
      })
    } catch {
      // rendered below
    }
  }

  const answer = pickText(comparison.data)
  const citations = pickCitations(comparison.data)
  const error = comparison.error ? describeError(comparison.error) : null

  return (
    <Card>
      <CardHeader title="Company comparison" description="Compare companies or metrics across documents." />
      <CardBody className="flex flex-col gap-3">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Company A" id="company-a" value={companyA} onChange={(event) => setCompanyA(event.target.value)} placeholder="e.g. Apple" />
            <Input label="Company B" id="company-b" value={companyB} onChange={(event) => setCompanyB(event.target.value)} placeholder="e.g. Netflix" />
          </div>
          <Input
            label="Question (optional)"
            id="comparison-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. Compare gross margin"
          />
          <div>
            <Button type="submit" loading={comparison.isPending} loadingLabel="Comparing">
              Compare
            </Button>
          </div>
        </form>

        {error ? (
          <Alert tone="danger" title="Comparison failed" code={error.code}>
            {error.message}
          </Alert>
        ) : null}

        {comparison.isPending ? <SkeletonText lines={6} /> : null}

        {comparison.data && !comparison.isPending ? (
          <div className="flex flex-col gap-3">
            {answer ? (
              <div className="rounded-card border border-line bg-surface-muted/40 p-4 text-body text-ink whitespace-pre-wrap">
                {answer}
              </div>
            ) : (
              <EmptyState title="No comparison text returned" description="The API returned a result without readable text." />
            )}
            {citations.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {citations.map((citation, index) => (
                  <li key={index} className="rounded-card border border-line bg-surface p-3 text-caption text-ink-muted">
                    <span className="font-mono text-ink-subtle">[{index + 1}]</span>{' '}
                    {String(citation.document_title ?? citation.title ?? citation.document_id ?? 'Source')}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </CardBody>
    </Card>
  )
}

