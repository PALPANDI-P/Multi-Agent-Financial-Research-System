import { Link } from 'react-router-dom'
import type { WorkspaceRead } from '../../api/types'
import { Card, CardBody } from '../../components'
import { ArrowRightIcon, DocumentIcon, WorkspaceIcon } from '../../components/icons'
import { formatDateTime, formatNumber } from '../../lib/format'

export interface WorkspaceCardProps {
  workspace: WorkspaceRead
}

/**
 * One workspace of the listing.
 *
 * The card has one reading order: the name, then the sentence that explains
 * it, then the three figures that came from the API, and finally the action.
 * The action is the only thing that moves on hover, so the pointer always
 * knows where the card goes.
 */
export function WorkspaceCard({ workspace }: WorkspaceCardProps) {
  return (
    <Card interactive className="group flex h-full flex-col">
      <CardBody className="flex h-full flex-col gap-4 p-5 sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <h3 className="min-w-0 text-subtitle font-semibold text-ink">
            <Link
              to={`/app/workspaces/${workspace.id}`}
              className="rounded-xs transition-colors duration-150 hover:text-brand-700 focus-visible:text-brand-700"
            >
              {workspace.name}
            </Link>
          </h3>
          <span
            aria-hidden="true"
            className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-line bg-surface-muted text-ink-subtle transition-colors duration-200 group-hover:border-brand-200 group-hover:bg-brand-50 group-hover:text-brand-700"
          >
            <WorkspaceIcon size={16} />
          </span>
        </div>

        {workspace.description ? (
          <p className="line-clamp-2 text-small leading-relaxed text-ink-muted">
            {workspace.description}
          </p>
        ) : (
          <p className="text-small text-ink-subtle italic">No description</p>
        )}

        <dl className="mt-auto grid grid-cols-2 gap-x-4 gap-y-3 border-t border-line-faint pt-4 text-caption sm:grid-cols-3">
          <div>
            <dt className="flex items-center gap-1.5 text-ink-subtle">
              <DocumentIcon size={12} />
              Documents
            </dt>
            <dd className="mt-1 font-mono text-small font-semibold text-ink tabular-nums">
              {formatNumber(workspace.document_count)}
            </dd>
          </div>
          <div>
            <dt className="text-ink-subtle">Created</dt>
            <dd className="mt-1 font-mono text-ink-muted tabular-nums">
              {formatDateTime(workspace.created_at)}
            </dd>
          </div>
          <div>
            <dt className="text-ink-subtle">Updated</dt>
            <dd className="mt-1 font-mono text-ink-muted tabular-nums">
              {formatDateTime(workspace.updated_at)}
            </dd>
          </div>
        </dl>

        <Link
          to={`/app/workspaces/${workspace.id}`}
          className="inline-flex w-fit items-center gap-1.5 rounded-xs text-small font-medium text-brand-700 transition-colors duration-150 hover:text-brand-600"
        >
          Open workspace
          <ArrowRightIcon
            size={15}
            className="transition-transform duration-200 ease-out-soft group-hover:translate-x-1"
          />
        </Link>
      </CardBody>
    </Card>
  )
}