import { useState } from 'react'
import type { SearchResultItem } from '../../api/types'
import { Badge } from '../../components'
import { ChevronDownIcon, HashIcon, TableIcon } from '../../components/icons'
import { cn } from '../../lib/cn'
import {
  formatMetadataValue,
  formatPageRange,
  formatScore,
  humanizeKey,
} from '../../lib/format'

export interface SearchResultCardProps {
  result: SearchResultItem
  /** The position of the hit in the result list, used as the citation mark. */
  index?: number
}

/** Above this length the passage is folded away behind a disclosure. */
const LONG_PASSAGE = 420

/**
 * One hit of a search.
 *
 * The card is a citation reader.  The reference runs along the top - the
 * document, the chunk type, the score - and the citation runs down the
 * left: the page is the reference, the section heading is the context and
 * the passage is the evidence.  The raw metadata waits behind a disclosure.
 */
export function SearchResultCard({ result, index }: SearchResultCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const metadataEntries = Object.entries(result.metadata ?? {})
  const citationMark = index === undefined ? null : String(index + 1).padStart(2, '0')
  const isLong = result.content.length > LONG_PASSAGE

  return (
    <article className="overflow-hidden rounded-card border border-line bg-surface shadow-card transition-[box-shadow,border-color] duration-200 hover:border-line-strong hover:shadow-raised">
      {/* The reference: which document, and how well it matched. */}
      <header className="flex flex-wrap items-start justify-between gap-x-5 gap-y-3 border-b border-line-faint bg-surface-muted/40 px-4 py-3.5 sm:px-5">
        <div className="flex min-w-0 items-start gap-3">
          {citationMark ? (
            <span
              aria-hidden="true"
              className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-xs border border-line bg-surface font-mono text-caption text-ink-subtle tabular-nums"
            >
              {citationMark}
            </span>
          ) : null}
          <div className="min-w-0">
            <h4 className="font-display text-subtitle text-ink">
              <span className="line-clamp-1" title={result.document_title ?? undefined}>
                {result.document_title ?? 'Untitled document'}
              </span>
            </h4>
            <p className="mt-1 truncate font-mono text-micro text-ink-subtle">
              {result.company_name ?? 'No company'} · {result.document_type ?? 'No type'} ·{' '}
              {result.fiscal_period ?? 'No fiscal period'}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <Badge tone={result.chunk_type === 'table' ? 'info' : 'neutral'} title="chunk_type">
            <span className="flex items-center gap-1 font-mono text-micro">
              {result.chunk_type === 'table' ? <TableIcon size={12} /> : null}
              {result.chunk_type}
            </span>
          </Badge>
          <span className="flex items-baseline gap-1.5">
            <span className="text-micro tracking-[0.1em] text-ink-subtle uppercase">score</span>
            <span
              title="relevance score"
              className="font-mono text-small font-semibold text-ink tabular-nums"
            >
              {formatScore(result.score)}
            </span>
          </span>
        </div>
      </header>

      {/* The citation: the page reference in its own gutter, the section and
          the passage beside it. */}
      <div className="grid gap-x-6 gap-y-3 px-4 py-5 sm:grid-cols-[5.25rem_minmax(0,1fr)] sm:px-5 sm:py-6">
        <div className="flex items-center gap-2 sm:block">
          <span className="inline-flex shrink-0 items-center rounded-xs border border-brand-200 bg-brand-50 px-2 py-0.5 font-mono text-caption font-semibold text-brand-800">
            {formatPageRange(result.page_start, result.page_end)}
          </span>
        </div>

        <div className="min-w-0">
          <p
            title={result.section_heading ?? undefined}
            className="text-small font-semibold text-ink"
          >
            {result.section_heading ?? 'No section heading'}
          </p>

          <div className="mt-3.5 border-l border-line pl-4 sm:pl-5">
            <p
              className={cn(
                'max-w-[68ch] font-display text-reading leading-[1.75] whitespace-pre-wrap text-ink',
                isLong && !isExpanded && 'line-clamp-7 fade-bottom',
              )}
            >
              {result.content}
            </p>
          </div>

          {isLong ? (
            <button
              type="button"
              aria-expanded={isExpanded}
              onClick={() => setIsExpanded((open) => !open)}
              className="mt-3 rounded-xs text-caption font-medium text-brand-700 transition-colors duration-150 hover:text-brand-600"
            >
              <span className="link-underline">
                {isExpanded ? 'Show less' : 'Show the whole passage'}
              </span>
            </button>
          ) : null}
        </div>
      </div>

      {/* The identifiers and the raw metadata wait behind a disclosure. */}
      <footer className="border-t border-line-faint px-4 py-3 text-caption sm:px-5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="font-mono text-micro text-ink-subtle">doc {result.document_id}</span>
          <span className="inline-flex items-center gap-1 font-mono text-micro text-ink-subtle">
            <HashIcon size={11} />
            {result.chunk_id}
          </span>
        </div>

        {metadataEntries.length > 0 ? (
          <details className="group mt-2">
            <summary className="flex w-fit cursor-pointer items-center gap-1.5 rounded-xs text-ink-muted transition-colors duration-150 hover:text-ink">
              Source metadata
              <span className="font-mono text-ink-subtle">({metadataEntries.length})</span>
              <ChevronDownIcon
                size={13}
                className="transition-transform duration-200 group-open:rotate-180"
              />
            </summary>
            <dl className="mt-3 grid gap-x-6 gap-y-1.5 text-caption sm:grid-cols-2">
              {metadataEntries.map(([key, value]) => (
                <div key={key} className="flex min-w-0 gap-1.5">
                  <dt className="shrink-0 text-ink-subtle">{humanizeKey(key)}:</dt>
                  <dd className="min-w-0 break-all font-mono text-ink">{formatMetadataValue(value)}</dd>
                </div>
              ))}
            </dl>
          </details>
        ) : null}
      </footer>
    </article>
  )
}