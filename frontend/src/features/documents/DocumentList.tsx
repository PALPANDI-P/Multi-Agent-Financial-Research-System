import { useState } from 'react'
import type { ReactNode } from 'react'
import type { DocumentRead } from '../../api/types'
import {
  Badge,
  Button,
  EmptyState,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
} from '../../components'
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

  if (!isLoading && documents.length === 0) {
    return (
      <EmptyState
        title="No documents in this workspace yet"
        description="Upload a file above to start ingesting research documents. Everything shown in this list comes from the API."
        action={emptyAction}
      />
    )
  }

  return (
    <>
      {/* Wide viewports: a real table. */}
      <div className="hidden lg:block">
        <Table caption="Documents in this workspace">
          <TableHead>
            <TableRow>
              <TableHeadCell>Company</TableHeadCell>
              <TableHeadCell>Title</TableHeadCell>
              <TableHeadCell>Type</TableHeadCell>
              <TableHeadCell>Fiscal period</TableHeadCell>
              <TableHeadCell>Filename</TableHeadCell>
              <TableHeadCell>Size</TableHeadCell>
              <TableHeadCell>Pages</TableHeadCell>
              <TableHeadCell>Status</TableHeadCell>
              <TableHeadCell>Chunks</TableHeadCell>
              <TableHeadCell>Error</TableHeadCell>
              <TableHeadCell>Updated</TableHeadCell>
              <TableHeadCell>Actions</TableHeadCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {documents.map((document) => (
              <TableRow key={document.id}>
                <TableCell>{document.company_name ?? '—'}</TableCell>
                <TableCell className="font-medium">{document.document_title ?? '—'}</TableCell>
                <TableCell>{document.document_type ?? '—'}</TableCell>
                <TableCell>{document.fiscal_period ?? '—'}</TableCell>
                <TableCell>
                  <span className="break-all font-mono text-xs">{document.original_filename}</span>
                </TableCell>
                <TableCell>{formatBytes(document.file_size_bytes)}</TableCell>
                <TableCell>{document.page_count ?? '—'}</TableCell>
                <TableCell>
                  <DocumentStatusBadge
                    status={document.processing_status}
                    stage={document.processing_stage}
                  />
                </TableCell>
                <TableCell>{formatNumber(document.chunk_count)}</TableCell>
                <TableCell>
                  {document.error_code || document.error_message ? (
                    <span className="block max-w-56">
                      {document.error_code ? (
                        <Badge tone="danger" className="mb-1">
                          <span className="font-mono">{document.error_code}</span>
                        </Badge>
                      ) : null}
                      {document.error_message ? (
                        <span className="block text-xs text-danger-700">
                          {document.error_message}
                        </span>
                      ) : null}
                    </span>
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs text-ink-muted">
                  {formatDateTime(document.updated_at)}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-2">
                    {isFailedStatus(document.processing_status) ? (
                      <Button
                        variant="secondary"
                        size="sm"
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
                      onClick={() => setPendingRemoval(document)}
                    >
                      Remove
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Narrow viewports: stacked cards, same data, no horizontal scroll. */}
      <ul className="divide-y divide-line lg:hidden">
        {documents.map((document) => (
          <li key={document.id} className="px-4 py-4 sm:px-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">
                  {document.document_title ?? document.original_filename}
                </p>
                <p className="mt-0.5 text-xs text-ink-subtle">
                  {document.company_name ?? 'No company'} ·{' '}
                  {document.document_type ?? 'No type'} ·{' '}
                  {document.fiscal_period ?? 'No fiscal period'}
                </p>
              </div>
              <DocumentStatusBadge
                status={document.processing_status}
                stage={document.processing_stage}
              />
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
              <div>
                <dt className="text-ink-subtle">Filename</dt>
                <dd className="break-all font-mono text-ink">{document.original_filename}</dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Size</dt>
                <dd className="text-ink">{formatBytes(document.file_size_bytes)}</dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Pages</dt>
                <dd className="text-ink">{document.page_count ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Chunks</dt>
                <dd className="text-ink">{formatNumber(document.chunk_count)}</dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Created</dt>
                <dd className="text-ink">{formatDateTime(document.created_at)}</dd>
              </div>
              <div>
                <dt className="text-ink-subtle">Updated</dt>
                <dd className="text-ink">{formatDateTime(document.updated_at)}</dd>
              </div>
            </dl>

            {document.error_code || document.error_message ? (
              <div className="mt-3 rounded-control border border-danger-200 bg-danger-50 px-3 py-2">
                {document.error_code ? (
                  <p className="font-mono text-xs font-semibold text-danger-700">
                    {document.error_code}
                  </p>
                ) : null}
                {document.error_message ? (
                  <p className="text-xs text-danger-700">{document.error_message}</p>
                ) : null}
              </div>
            ) : null}

            <div className="mt-3 flex flex-wrap gap-2">
              {isFailedStatus(document.processing_status) ? (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={retryingDocumentId === document.id}
                  loadingLabel="Retrying…"
                  onClick={() => onRetry(document)}
                >
                  Retry
                </Button>
              ) : null}
              <Button variant="ghost" size="sm" onClick={() => setPendingRemoval(document)}>
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


