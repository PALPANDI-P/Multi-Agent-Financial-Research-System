import { Link } from 'react-router-dom'
import type { WorkspaceRead } from '../../api/types'
import { Card, CardBody } from '../../components'
import { formatDateTime, formatNumber, truncate } from '../../lib/format'

export interface WorkspaceCardProps {
  workspace: WorkspaceRead
}

export function WorkspaceCard({ workspace }: WorkspaceCardProps) {
  return (
    <Card className="flex h-full flex-col transition-shadow hover:shadow-md">
      <CardBody className="flex h-full flex-col gap-3">
        <div className="flex-1">
          <h3 className="text-base font-semibold text-ink">
            <Link
              to={`/workspaces/${workspace.id}`}
              className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 focus-visible:ring-offset-surface hover:text-brand-700"
            >
              {workspace.name}
            </Link>
          </h3>
          {workspace.description ? (
            <p className="mt-1.5 text-sm text-ink-muted">
              {truncate(workspace.description, 220)}
            </p>
          ) : (
            <p className="mt-1.5 text-sm italic text-ink-subtle">No description</p>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-line pt-3 text-xs sm:grid-cols-3">
          <div>
            <dt className="text-ink-subtle">Documents</dt>
            <dd className="font-semibold text-ink">{formatNumber(workspace.document_count)}</dd>
          </div>
          <div>
            <dt className="text-ink-subtle">Created</dt>
            <dd className="text-ink">{formatDateTime(workspace.created_at)}</dd>
          </div>
          <div>
            <dt className="text-ink-subtle">Last updated</dt>
            <dd className="text-ink">{formatDateTime(workspace.updated_at)}</dd>
          </div>
        </dl>

        <div>
          <Link
            to={`/workspaces/${workspace.id}`}
            className="inline-flex items-center gap-1 rounded text-sm font-medium text-brand-700 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
          >
            Open workspace
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </CardBody>
    </Card>
  )
}
