import type { SearchResultItem } from '../../api/types'
import { Badge } from '../../components'
import {
  formatMetadataValue,
  formatPageRange,
  formatScore,
  humanizeKey,
} from '../../lib/format'

export interface SearchResultCardProps {
  result: SearchResultItem
}

export function SearchResultCard({ result }: SearchResultCardProps) {
  const metadataEntries = Object.entries(result.metadata ?? {})

  return (
    <article className="rounded-card border border-line bg-surface p-4 sm:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-ink">
            {result.document_title ?? 'Untitled document'}
          </h4>
          <p className="mt-0.5 text-xs text-ink-muted">
            {result.company_name ?? 'No company'} · {result.document_type ?? 'No type'} ·{' '}
            {result.fiscal_period ?? 'No fiscal period'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" title="chunk_type">
            <span className="font-mono">{result.chunk_type}</span>
          </Badge>
          <Badge tone="info" title="relevance score">
            score <span className="font-mono">{formatScore(result.score)}</span>
          </Badge>
        </div>
      </header>

      <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
        <div className="flex gap-1">
          <dt>Pages:</dt>
          <dd className="font-medium text-ink">
            {formatPageRange(result.page_start, result.page_end)}
          </dd>
        </div>
        <div className="flex gap-1">
          <dt>Section:</dt>
          <dd className="font-medium text-ink">{result.section_heading ?? '—'}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Document ID:</dt>
          <dd className="font-mono font-medium text-ink">{result.document_id}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Chunk ID:</dt>
          <dd className="font-mono font-medium text-ink">{result.chunk_id}</dd>
        </div>
      </dl>

      <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink">{result.content}</p>

      {metadataEntries.length > 0 ? (
        <details className="mt-3 rounded-control border border-line bg-surface-muted px-3 py-2">
          <summary className="cursor-pointer text-xs font-semibold text-ink-muted">
            Source metadata ({metadataEntries.length})
          </summary>
          <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
            {metadataEntries.map(([key, value]) => (
              <div key={key} className="flex min-w-0 gap-1">
                <dt className="shrink-0 text-ink-subtle">{humanizeKey(key)}:</dt>
                <dd className="min-w-0 break-all font-mono text-ink">
                  {formatMetadataValue(value)}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}
    </article>
  )
}
