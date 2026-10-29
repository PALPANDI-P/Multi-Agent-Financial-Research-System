import { useMemo } from 'react'
import { describeError } from '../../api/client'
import { Alert, Badge, Card, CardBody, CardHeader, EmptyState, SkeletonRows } from '../../components'
import { useDocuments } from '../../hooks/useDocuments'
import { DocumentStatusBadge } from '../../features/documents/DocumentStatusBadge'

export interface ProcessingStatusTrackerProps {
  workspaceId: string
}

export function ProcessingStatusTracker({ workspaceId }: ProcessingStatusTrackerProps) {
  const documentsQuery = useDocuments(workspaceId, { limit: 100, offset: 0 })
  const documents = documentsQuery.data?.items ?? []
  const error = documentsQuery.error ? describeError(documentsQuery.error) : null

  const counts = useMemo(() => {
    const result: Record<string, number> = {}
    for (const doc of documents) {
      result[doc.processing_status] = (result[doc.processing_status] ?? 0) + 1
    }
    return result
  }, [documents])

  return (
    <Card>
      <CardHeader title="Processing status" description="Track document ingestion progress." />
      <CardBody className="flex flex-col gap-3">
        {error ? (
          <Alert tone="danger" title="Status could not be loaded" code={error.code}>
            {error.message}
          </Alert>
        ) : null}

        {documentsQuery.isPending ? <SkeletonRows rows={4} /> : null}

        {!documentsQuery.isPending && documents.length === 0 ? (
          <EmptyState title="No documents" description="Upload documents to track processing." />
        ) : null}

        {Object.keys(counts).length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {Object.entries(counts).map(([status, count]) => (
              <Badge key={status} tone="neutral">
                {status}: {count}
              </Badge>
            ))}
          </div>
        ) : null}

        {documents.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {documents.map((document) => (
              <li key={document.id} className="flex items-center justify-between gap-3 rounded-card border border-line bg-surface p-3">
                <span className="truncate text-small text-ink">{document.original_filename}</span>
                <DocumentStatusBadge status={document.processing_status} stage={document.processing_stage} />
              </li>
            ))}
          </ul>
        ) : null}
      </CardBody>
    </Card>
  )
}

