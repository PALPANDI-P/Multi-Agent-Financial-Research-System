import { cn } from '../lib/cn'
import { formatNumber } from '../lib/format'
import { Button } from './Button'
import { Select } from './Select'

export interface PaginationProps {
  total: number
  limit: number
  offset: number
  onOffsetChange: (offset: number) => void
  onLimitChange?: (limit: number) => void
  pageSizeOptions?: number[]
  itemLabel?: string
  disabled?: boolean
  className?: string
}

export function Pagination({
  total,
  limit,
  offset,
  onOffsetChange,
  onLimitChange,
  pageSizeOptions = [10, 25, 50, 100],
  itemLabel = 'items',
  disabled = false,
  className,
}: PaginationProps) {
  const safeLimit = limit > 0 ? limit : 10
  const totalPages = Math.max(1, Math.ceil(total / safeLimit))
  const currentPage = Math.min(totalPages, Math.floor(offset / safeLimit) + 1)
  const firstItem = total === 0 ? 0 : offset + 1
  const lastItem = Math.min(total, offset + safeLimit)
  const canGoBack = offset > 0
  const canGoForward = offset + safeLimit < total

  return (
    <nav
      aria-label="Pagination"
      className={cn(
        'flex flex-col gap-3 border-t border-line bg-surface-muted/40 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-6',
        className,
      )}
    >
      <p className="text-small text-ink-muted" aria-live="polite">
        {total === 0
          ? `No ${itemLabel}`
          : `Showing ${formatNumber(firstItem)}–${formatNumber(lastItem)} of ${formatNumber(total)} ${itemLabel}`}
      </p>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {onLimitChange ? (
          <div className="w-36">
            <Select
              label="Per page"
              id="pagination-page-size"
              className="h-9 text-small"
              value={String(safeLimit)}
              disabled={disabled}
              onChange={(event) => {
                const nextLimit = Number(event.target.value)
                onLimitChange(nextLimit)
              }}
              options={pageSizeOptions.map((size) => ({
                value: String(size),
                label: `${size} per page`,
              }))}
            />
          </div>
        ) : null}

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={disabled || !canGoBack}
            onClick={() => onOffsetChange(Math.max(0, offset - safeLimit))}
          >
            Previous
          </Button>
          <span className="text-small whitespace-nowrap text-ink-muted">
            Page{' '}
            <span className="font-mono font-semibold text-ink tabular-nums">
              {formatNumber(currentPage)}
            </span>{' '}
            <span className="text-ink-subtle">of</span>{' '}
            <span className="font-mono tabular-nums">{formatNumber(totalPages)}</span>
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={disabled || !canGoForward}
            onClick={() => onOffsetChange(offset + safeLimit)}
          >
            Next
          </Button>
        </div>
      </div>
    </nav>
  )
}