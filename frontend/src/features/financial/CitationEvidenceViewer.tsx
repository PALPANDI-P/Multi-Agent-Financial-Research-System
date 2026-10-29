import { useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import { Alert, Button, Card, CardBody, CardHeader, EmptyState, Input, SkeletonRows } from '../../components'
import { useValidateCitation } from '../../hooks/useFinancial'
import { listCitations } from '../../api/financial'

export interface CitationEvidenceViewerProps {
  workspaceId: string
}

export function CitationEvidenceViewer({ workspaceId }: CitationEvidenceViewerProps) {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; code: string } | null>(null)
  const [citationJson, setCitationJson] = useState('')
  const validate = useValidateCitation()

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await listCitations(workspaceId, { limit: 100 })
      setItems(response.items ?? [])
    } catch (caught) {
      const described = describeError(caught)
      setError(described)
    } finally {
      setLoading(false)
    }
  }

  const handleValidate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    try {
      const parsed = citationJson.trim() ? JSON.parse(citationJson) : {}
      const result = await validate.mutateAsync(parsed)
      if (result.valid) {
        setError(null)
      } else {
        setError({ message: result.errors.join(', ') || 'Invalid citation', code: 'invalid_citation' })
      }
    } catch (caught) {
      const described = describeError(caught)
      setError(described)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Citations & evidence"
        description="Browse and validate citations for this workspace."
        actions={
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            Load citations
          </Button>
        }
      />
      <CardBody className="flex flex-col gap-3">
        {error ? (
          <Alert tone="danger" title="Citation error" code={error.code}>
            {error.message}
          </Alert>
        ) : null}

        {loading ? <SkeletonRows rows={4} /> : null}

        {!loading && items.length === 0 ? (
          <EmptyState title="No citations loaded" description="Click Load citations to fetch evidence." />
        ) : null}

        {items.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {items.map((item, index) => (
              <li key={index} className="rounded-card border border-line bg-surface p-3 text-caption text-ink-muted">
                <span className="font-mono text-ink-subtle">[{index + 1}]</span>{' '}
                {String(item.document_title ?? item.title ?? item.document_id ?? 'Citation')}
                {typeof item.content === 'string' ? <p className="mt-1 text-ink">{item.content}</p> : null}
              </li>
            ))}
          </ul>
        ) : null}

        <form onSubmit={handleValidate} className="flex flex-col gap-2">
          <Input
            label="Validate citation (JSON)"
            id="citation-json"
            value={citationJson}
            onChange={(event) => setCitationJson(event.target.value)}
            placeholder='{"chunk_id":"..."}'
          />
          <div>
            <Button type="submit" loading={validate.isPending} variant="secondary">
              Validate
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  )
}

