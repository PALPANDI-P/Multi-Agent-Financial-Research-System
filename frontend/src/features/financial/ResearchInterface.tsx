import { useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import { Alert, Button, Card, CardBody, CardHeader, Chip, EmptyState, Input } from '../../components'
import { useResearch } from '../../hooks/useFinancial'
import type { FinancialAgentResult } from '../../api/types'

export interface ResearchInterfaceProps {
  workspaceId: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  citations: Array<Record<string, unknown>>
  createdAt: string
}

const SUGGESTED_QUESTIONS = [
  'What drove revenue growth in the uploaded documents?',
  'Summarize the key financial metrics and red flags.',
  'What are the main risks highlighted in the sample document?',
  'Compare gross margin trends across documents.',
]

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

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function ResearchInterface({ workspaceId }: ResearchInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const research = useResearch(workspaceId)

  const submitQuestion = async (raw: string) => {
    const trimmed = raw.trim()
    if (!trimmed) {
      setValidationError('Enter a research question.')
      return
    }
    setValidationError(null)
    const userMessage: ChatMessage = {
      id: makeId(),
      role: 'user',
      text: trimmed,
      citations: [],
      createdAt: new Date().toISOString(),
    }
    setMessages((previous) => [...previous, userMessage])
    setQuestion('')
    try {
      const result = await research.mutateAsync({ question: trimmed })
      const assistantMessage: ChatMessage = {
        id: makeId(),
        role: 'assistant',
        text: pickText(result),
        citations: pickCitations(result),
        createdAt: new Date().toISOString(),
      }
      setMessages((previous) => [...previous, assistantMessage])
    } catch {
      void 0
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await submitQuestion(question)
  }

  const handleClear = () => {
    setMessages([])
    setExpanded(new Set())
    research.reset()
  }

  const toggleCitations = (id: string) => {
    setExpanded((previous) => {
      const next = new Set(previous)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const error = research.error ? describeError(research.error) : null

  return (
    <Card>
      <CardHeader
        title="Research"
        description="Ask natural-language questions over the workspace."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={handleClear}
            disabled={messages.length === 0 && !research.error}
          >
            Clear chat
          </Button>
        }
      />
      <CardBody className="flex flex-col gap-3">
        {messages.length === 0 && !research.isPending ? (
          <EmptyState
            title="Start a research conversation"
            description="Ask questions about your workspace documents."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTED_QUESTIONS.map((suggested) => (
                  <Chip key={suggested} onClick={() => void submitQuestion(suggested)}>
                    {suggested}
                  </Chip>
                ))}
              </div>
            }
          />
        ) : null}

        {messages.length > 0 ? (
          <div className="flex flex-col gap-3">
            {messages.map((message) => (
              <div
                key={message.id}
                className={
                  message.role === 'user'
                    ? 'ml-auto max-w-[85%] rounded-card border border-brand-200 bg-brand-50 px-4 py-3 text-body text-ink'
                    : 'max-w-[90%] rounded-card border border-line bg-surface-muted/40 px-4 py-3 text-body text-ink'
                }
              >
                <p className="whitespace-pre-wrap">{message.text || (message.role === 'assistant' ? 'No answer text returned' : '')}</p>
                {message.role === 'assistant' && message.citations.length > 0 ? (
                  <div className="mt-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleCitations(message.id)}
                    >
                      {expanded.has(message.id) ? 'Hide' : 'Show'} citations ({message.citations.length})
                    </Button>
                    {expanded.has(message.id) ? (
                      <ul className="mt-2 flex flex-col gap-2">
                        {message.citations.map((citation, index) => (
                          <li
                            key={index}
                            className="rounded-card border border-line bg-surface p-3 text-caption text-ink-muted"
                          >
                            <span className="font-mono text-ink-subtle">[{index + 1}]</span>{' '}
                            {String(citation.document_title ?? citation.title ?? citation.document_id ?? 'Source')}
                            {citation.page_start ? `  p.${String(citation.page_start)}` : ''}
                            {typeof citation.content === 'string' ? (
                              <p className="mt-1 text-ink">{citation.content}</p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}

            {research.isPending ? (
              <div className="flex items-center gap-1.5 rounded-card border border-line bg-surface-muted/40 px-4 py-3 text-small text-ink-muted">
                <span className="h-2 w-2 animate-bounce rounded-full bg-ink-subtle [animation-delay:-0.3s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-ink-subtle [animation-delay:-0.15s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-ink-subtle" />
                <span className="sr-only">Researching…</span>
              </div>
            ) : null}
          </div>
        ) : null}

        {error ? (
          <Alert tone="danger" title="Research failed" code={error.code}>
            {error.message}
          </Alert>
        ) : null}

        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <div className="flex-1">
            <Input
              label="Research question"
              id="research-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              error={validationError}
              placeholder="e.g. What drove revenue growth?"
              disabled={research.isPending}
            />
          </div>
          <Button type="submit" loading={research.isPending} loadingLabel="Researching">
            Send
          </Button>
        </form>
      </CardBody>
    </Card>
  )
}
