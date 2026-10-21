import { useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import { Alert, Button, EmptyState, Input, Select } from '../../components'
import { useWorkspaceSearch } from '../../hooks/useSearch'
import { formatDuration, formatNumber } from '../../lib/format'
import { SearchResultCard } from './SearchResultCard'

export interface SearchPanelProps {
  workspaceId: string
}

const CHUNK_TYPE_OPTIONS = [
  { value: 'all', label: 'All chunk types' },
  { value: 'text', label: 'Text only' },
  { value: 'table', label: 'Tables only' },
]

const LIMIT_OPTIONS = [
  { value: '10', label: '10 results' },
  { value: '20', label: '20 results' },
  { value: '50', label: '50 results' },
]

export function SearchPanel({ workspaceId }: SearchPanelProps) {
  const [query, setQuery] = useState('')
  const [chunkType, setChunkType] = useState('all')
  const [limit, setLimit] = useState('10')
  const [validationError, setValidationError] = useState<string | null>(null)

  const search = useWorkspaceSearch(workspaceId)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) {
      setValidationError('Enter a search query.')
      return
    }
    setValidationError(null)

    const chunkTypes = chunkType === 'all' ? undefined : [chunkType]
    try {
      await search.mutateAsync({
        query: trimmed,
        limit: Number(limit),
        ...(chunkTypes ? { chunk_types: chunkTypes } : {}),
      })
    } catch {
      // The error is rendered from the mutation state below.
    }
  }

  const response = search.data
  const error = search.error ? describeError(search.error) : null

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Input
          label="Search this workspace"
          id="workspace-search-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          error={validationError}
          placeholder="e.g. revenue growth by segment"
          hint="Searches the indexed passages of this workspace. Results come straight from the API."
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Chunk type"
            id="workspace-search-chunk-type"
            value={chunkType}
            onChange={(event) => setChunkType(event.target.value)}
            options={CHUNK_TYPE_OPTIONS}
          />
          <Select
            label="Maximum results"
            id="workspace-search-limit"
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
            options={LIMIT_OPTIONS}
          />
        </div>

        <div>
          <Button type="submit" loading={search.isPending} loadingLabel="Searching…">
            Search
          </Button>
        </div>
      </form>

      {error ? (
        <Alert tone="danger" title="The search request failed" code={error.code}>
          {error.message}
        </Alert>
      ) : null}

      {response ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
            <span aria-live="polite">
              <span className="font-semibold text-ink">{formatNumber(response.total)}</span> result
              {response.total === 1 ? '' : 's'} for{' '}
              <span className="font-medium text-ink">“{response.query}”</span>
            </span>
            <span aria-live="polite">· took {formatDuration(response.took_ms)}</span>
          </div>

          {response.results.length === 0 ? (
            <EmptyState
              title="No results found"
              description={
                <>
                  The API returned no passages for this query in this workspace. Try different
                  wording, or widen the chunk-type filter.
                </>
              }
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {response.results.map((result) => (
                <li key={result.chunk_id}>
                  <SearchResultCard result={result} />
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}

