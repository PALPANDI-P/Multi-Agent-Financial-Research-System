import { Badge } from '../../components/Badge'
import { statusTone } from './documentStatus'

export interface DocumentStatusBadgeProps {
  status: string
  stage?: string | null
}

/** Shows the verbatim `processing_status` value returned by the API. */
export function DocumentStatusBadge({ status, stage }: DocumentStatusBadgeProps) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      <Badge tone={statusTone(status)} title={`processing_status: ${status}`}>
        <span className="font-mono">{status}</span>
      </Badge>
      {stage ? (
        <span className="text-xs text-ink-subtle">
          stage: <span className="font-mono">{stage}</span>
        </span>
      ) : (
        <span className="text-xs text-ink-subtle">stage: —</span>
      )}
    </span>
  )
}
