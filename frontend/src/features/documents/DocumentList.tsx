import { useState } from 'react'
import type { ReactNode } from 'react'
import type { DocumentRead } from '../../api/types'
import {
  Button,
  EmptyState,
  SkeletonRows,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
  TableRowHeader,
} from '../../components'
import { RefreshIcon, TrashIcon } from '../../components/icons'
import { formatBytes, formatDateTime, formatNumber } from '../../lib/format'
import { DeleteDocumentDialog } from './DeleteDocumentDialog'
import { DocumentStatusBadge } from './DocumentStatusBadge'
import { isFailedStatus } from './documentStatus'

export interface DocumentListProps {
  documents: DocumentRead[]
  workspaceId: string
  onRetry: (document: DocumentRead) => void
  retryingDocumentId?: string | null
  onRemoved?: (document: DocumentRead) => void
  isLoading?: boolean
  emptyAction?: ReactNode
}

/**
 * A timestamp split into its date and its time.
 *
 * The table has no room for "21 Oct 2026, 13:45" on one line, and a
 * two-line cell reads better than a clipped one.
 */
function formatTimestampParts(value: string): { date: string; time: string } {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return { date: '—', time: '' }
  const date = new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  }).format(parsed)
  const time = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
  return { date, time }
}

/**
 * The document list of a workspace.
 *
 * The table is the centrepiece of the workspace.  Its reading order is the
 * order of a citation: the filename first, in the mono face, because that is
 * the identifier a reader will quote.  The figures are tabular, the
 * separators are hairlines, and the actions only appear when the row is
 * reached - by pointer or by keyboard.
 */
export function DocumentList({
  documents,
  workspaceId,
  onRetry,
  retryingDocumentId,
  onRemoved,
  isLoading = false,
  emptyAction,
}: DocumentListProps) {
  const [pendingRemoval, setPendingRemoval] = useState<DocumentRead | null>(null)

  if (isLoading) {
    return <SkeletonRows rows={5} />
  }

  if (documents.length === 0) {
    return (
      <EmptyState
        title="No documents in this workspace yet"
        description="Upload a file to start ingesting research documents. Everything shown in this list comes from the API."
        action={emptyAction}
      />
    )
  }

  return (
    <>
      {/* Wide viewports: a real table. */}
      <div className="hidden lg:block">
        <Table caption="Documents in this workspace" minWidth="min-w-[60rem]">
          <TableHead>
            <TableRow>
              <TableHeadCell>Document</TableHeadCell>
              <TableHeadCell>Company</TableHeadCell>
              <TableHeadCell>Status</TableHeadCell>
              <TableHeadCell className="text-right">Pages</TableHeadCell>
              <TableHeadCell className="text-right">Chunks</TableHeadCell>
              <TableHeadCell className="text-right">Size</TableHeadCell>
              <TableHeadCell>Updated</TableHeadCell>
              <TableHeadCell className="text-right">
                <span className="sr-only">Actions</span>
              </TableHeadCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {documents.map((document) => {
              const updated = formatTimestampParts(document.updated_at)

              return (
                <TableRow key={document.id} className="group align-top hover:bg-surface-muted/80">
                  {/* The document: the filename is the identity and it is
                      printed in the mono face, the title is the second line. */}
                  <TableRowHeader className="w-[30%] border-l-[3px] border-transparent py-4 pl-5 transition-colors duration-150 group-hover:border-brand-500">
                    <p
                      title={document.original_filename}
                      className="truncate font-mono text-small font-medium text-ink"
                    >
                      {document.original_filename}
                    </p>
                    <p
                      title={document.document_title ?? undefined}
                      className="mt-1 line-clamp-1 text-caption text-ink-muted"
                    >
                      {document.document_title ?? 'Untitled document'}
                    </p>
                    <p className="mt-1.5 truncate font-mono text-micro text-ink-subtle">
                      {document.document_type ?? 'no type'}
                      {' · '}
                      {document.fiscal_period ?? 'no period'}
                    </p>
                    {document.error_code || document.error_message ? (
                      <p className="mt-2 flex items-start gap-1.5 border-l-2 border-danger-200 pl-2 text-caption text-danger-700">
                        {document.error_code ? (
                          <span className="font-mono font-semibold">{document.error_code}</span>
                        ) : null}
                        {document.error_message ? <span>{document.error_message}</span> : null}
                      </p>
                    ) : null}
                  </TableRowHeader>

                  <TableCell className="px-3 sm:px-4">
                    <span
                      title={document.company_name ?? undefined}
                      className="block truncate text-small text-ink-muted"
                    >
                      {document.company_name ?? '—'}
                    </span>
                  </TableCell>

                  <TableCell className="px-3 sm:px-4">
                    <DocumentStatusBadge
                      status={document.processing_status}
                      stage={document.processing_stage}
                    />
                  </TableCell>

                  <TableCell className="px-3 text-right font-mono text-small whitespace-nowrap text-ink tabular-nums sm:px-4">
                    {document.page_count ?? '—'}
                  </TableCell>

                  <TableCell className="px-3 text-right font-mono text-small whitespace-nowrap text-ink tabular-nums sm:px-4">
                    {formatNumber(document.chunk_count)}
                  </TableCell>

                  <TableCell className="px-3 text-right font-mono text-small whitespace-nowrap text-ink tabular-nums sm:px-4">
                    {formatBytes(document.file_size_bytes)}
                  </TableCell>

                  <TableCell className="px-3 font-mono text-caption whitespace-nowrap text-ink-muted tabular-nums sm:px-4">
                    <span className="block">{updated.date}</span>
                    {updated.time ? <span className="block">{updated.time}</span> : null}
                  </TableCell>

                  <TableCell className="px-3 sm:px-4">
                    <div className="flex shrink-0 items-center justify-end gap-1 whitespace-nowrap transition-opacity duration-150 lg:opacity-0 lg:group-hover:opacity-100 lg:focus-within:opacity-100">
                      {isFailedStatus(document.processing_status) ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="px-2.5"
                          leadingIcon={<RefreshIcon size={14} />}
                          loading={retryingDocumentId === document.id}
                          loadingLabel="Retrying…"
                          onClick={() => onRetry(document)}
                        >
                          Retry
                        </Button>
                      ) : null}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="px-2.5"
                        leadingIcon={<TrashIcon size={14} />}
                        onClick={() => setPendingRemoval(document)}
                      >
                        Remove
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {/* Narrow viewports: stacked cards, same data, no horizontal scroll. */}
      <ul className="divide-y divide-line lg:hidden">
        {documents.map((document) => (
          <li key={document.id} className="px-5 py-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p
                  title={document.original_filename}
                  className="truncate font-mono text-small font-medium text-ink"
                >
                  {document.original_filename}
                </p>
                <p className="mt-1 text-caption text-ink-muted">
                  {document.document_title ?? 'Untitled document'}
                </p>
              </div>
              <DocumentStatusBadge
                status={document.processing_status}
                stage={document.processing_stage}
              />
            </div>

            <p className="mt-2.5 font-mono text-micro text-ink-subtle">
              {document.company_name ?? 'No company'} · {document.document_type ?? 'No type'} ·{' '}
              {document.fiscal_period ?? 'No fiscal period'}
            </p>

            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-caption sm:grid-cols-3">
              <div>
                <dt className="text-ink-subtle">Size</dt>
                <dd className="mt-0.5 font-mono text-ink tabular-nums">
                  {formatBytes(document.file_size_bytes)}
                </dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Pages</dt>
                <dd className="mt-0.5 font-mono text-ink tabular-nums">
                  {document.page_count ?? '—'}
                </dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Chunks</dt>
                <dd className="mt-0.5 font-mono text-ink tabular-nums">
                  {formatNumber(document.chunk_count)}
                </dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Created</dt>
                <dd className="mt-0.5 text-ink">{formatDateTime(document.created_at)}</dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Updated</dt>
                <dd className="mt-0.5 text-ink">{formatDateTime(document.updated_at)}</dd>
              </div>
            </dl>

            {document.error_code || document.error_message ? (
              <div className="mt-4 rounded-control border border-danger-200 bg-danger-50/70 px-3 py-2.5">
                {document.error_code ? (
                  <p className="font-mono text-caption font-semibold text-danger-700">
                    {document.error_code}
                  </p>
                ) : null}
                {document.error_message ? (
                  <p className="mt-0.5 text-caption text-danger-700">{document.error_message}</p>
                ) : null}
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap gap-2">
              {isFailedStatus(document.processing_status) ? (
                <Button
                  variant="secondary"
                  size="sm"
                  leadingIcon={<RefreshIcon size={14} />}
                  loading={retryingDocumentId === document.id}
                  loadingLabel="Retrying…"
                  onClick={() => onRetry(document)}
                >
                  Retry
                </Button>
              ) : null}
              <Button
                variant="ghost"
                size="sm"
                leadingIcon={<TrashIcon size={14} />}
                onClick={() => setPendingRemoval(document)}
              >
                Remove
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <DeleteDocumentDialog
        open={pendingRemoval !== null}
        document={pendingRemoval}
        workspaceId={workspaceId}
        onClose={() => setPendingRemoval(null)}
        onDeleted={(document) => {
          setPendingRemoval(null)
          onRemoved?.(document)
        }}
      />
    </>
  )
}