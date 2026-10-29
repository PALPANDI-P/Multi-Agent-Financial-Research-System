import { useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import { Alert, Button, Card, CardBody, CardHeader, EmptyState, Input, SkeletonText } from '../../components'
import { useResearch } from '../../hooks/useFinancial'
import type { FinancialAgentResult } from '../../api/types'

export interface ResearchInterfaceProps {
  workspaceId: string
}

function pickText(result: FinancialAgentResult | undefined): string {
  if (!result) return ''
  const candidates = ['answer', 'final_answer', 'response', 'summary', 'answer_text', 'text']
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

export function ResearchInterface({ workspaceId }: ResearchInterfaceProps) {
  const [question, setQuestion] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const research = useResearch(workspaceId)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed) {
      setValidationError('Enter a research question.')
      return
    }
    setValidationError(null)
    try {
      await research.mutateAsync({ question: trimmed })
    } catch {
      // rendered below
    }
  }

  const answer = pickText(research.data)
  const citations = pickCitations(research.data)
  const error = research.error ? describeError(research.error) : null

  return (
    <Card>
      <CardHeader title="Research" description="Ask natural-language questions over the workspace." />
      <CardBody className="flex flex-col gap-3">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <Input
            label="Research question"
            id="research-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            error={validationError}
            placeholder="e.g. What drove revenue growth?"
          />
          <div>
            <Button type="submit" loading={research.isPending} loadingLabel="Researching">
              Ask
            </Button>
          </div>
        </form>

        {error ? (
          <Alert tone="danger" title="Research failed" code={error.code}>
            {error.message}
          </Alert>
        ) : null}

        {research.isPending ? <SkeletonText lines={6} /> : null}

        {research.data && !research.isPending ? (
          <div className="flex flex-col gap-3">
            {answer ? (
              <div className="rounded-card border border-line bg-surface-muted/40 p-4 text-body text-ink whitespace-pre-wrap">
                {answer}
              </div>
            ) : (
              <EmptyState title="No answer text returned" description="The API returned a result without a readable answer." />
            )}

            {citations.length > 0 ? (
              <div>
                <h3 className="text-subtitle text-ink mb-2">Citations</h3>
                <ul className="flex flex-col gap-2">
                  {citations.map((citation, index) => (
                    <li key={index} className="rounded-card border border-line bg-surface p-3 text-caption text-ink-muted">
                      <span className="font-mono text-ink-subtle">[{index + 1}]</span>{' '}
                      {String(citation.document_title ?? citation.title ?? citation.document_id ?? 'Source')}
                      {citation.page_start ? `  p.${String(citation.page_start)}` : ''}
                      {typeof citation.content === 'string' ? (
                        <p className="mt-1 text-ink">{citation.content}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardBody>
    </Card>
  )
}

