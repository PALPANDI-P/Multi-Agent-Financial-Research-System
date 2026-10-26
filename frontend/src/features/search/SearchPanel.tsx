import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import { Alert, Button, EmptyState, Input, Select } from '../../components'
import { SearchIcon } from '../../components/icons'
import { useWorkspaceSearch } from '../../hooks/useSearch'
import { formatDuration, formatNumber } from '../../lib/format'
import { SearchResultCard } from './SearchResultCard'

export interface SearchPanelProps {
  workspaceId: string
  /** A query that is pre-filled, e.g. from a suggested query of a scenario. */
  initialQuery?: string
  /** Run the search as soon as an initial query arrives. */
  autoSearch?: boolean
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

/** The shape of a result card, drawn while the request is in flight. */
function ResultSkeleton() {
  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <span className="skeleton block h-4 w-2/5" />
      <span className="skeleton mt-2 block h-3 w-1/4" />
      <span className="skeleton mt-4 block h-3 w-3/4" />
      <span className="skeleton mt-2 block h-3 w-full" />
      <span className="skeleton mt-2 block h-3 w-5/6" />
    </div>
  )
}

export function SearchPanel({
  workspaceId,
  initialQuery = '',
  autoSearch = false,
}: SearchPanelProps) {
  const [query, setQuery] = useState(initialQuery)
  const [chunkType, setChunkType] = useState('all')
  const [limit, setLimit] = useState('10')
  const [validationError, setValidationError] = useState<string | null>(null)

  const search = useWorkspaceSearch(workspaceId)
  const { mutateAsync } = search
  const autoSearchedRef = useRef<string | null>(null)

  useEffect(() => {
    const trimmed = initialQuery.trim()
    if (!autoSearch || !trimmed) return
    if (autoSearchedRef.current === trimmed) return
    autoSearchedRef.current = trimmed
    void mutateAsync({ query: trimmed, limit: Number(limit) }).catch(() => {
      // The error is rendered from the mutation state below.
    })
  }, [autoSearch, initialQuery, limit, mutateAsync])

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
      await mutateAsync({
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
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem_11rem] sm:items-end">
          <Input
            label="Search this workspace"
            id="workspace-search-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            error={validationError}
            placeholder="e.g. revenue growth by segment"
          />
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

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            loading={search.isPending}
            loadingLabel="Searching…"
            leadingIcon={search.isPending ? undefined : <SearchIcon size={16} />}
          >
            Search
          </Button>
          <p className="text-caption text-ink-subtle">
            Searches the indexed passages of this workspace. Results come straight from the API.
          </p>
        </div>
      </form>

      {error ? (
        <Alert tone="danger" title="The search request failed" code={error.code}>
          {error.message}
        </Alert>
      ) : null}

      {search.isPending && !response ? (
        <div role="status" aria-live="polite">
          <span className="sr-only">Searching the workspace…</span>
          <ul className="flex flex-col gap-4" aria-hidden="true">
            {[0, 1, 2].map((index) => (
              <li key={index}>
                <ResultSkeleton />
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {response ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line pb-3 text-small text-ink-muted">
            <span aria-live="polite">
              <span className="font-mono font-semibold text-ink tabular-nums">
                {formatNumber(response.total)}
              </span>{' '}
              result{response.total === 1 ? '' : 's'} for{' '}
              <span className="font-medium text-ink">“{response.query}”</span>
            </span>
            <span aria-live="polite" className="font-mono text-caption text-ink-subtle">
              took {formatDuration(response.took_ms)}
            </span>
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
            <ul className="flex flex-col gap-4">
              {response.results.map((result, index) => (
                <li key={result.chunk_id}>
                  <SearchResultCard result={result} index={index} />
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}