import { Badge } from '../../components/Badge'
import { statusTone } from './documentStatus'

export interface DocumentStatusBadgeProps {
  status: string
  stage?: string | null
}

/**
 * Shows the verbatim `processing_status` value returned by the API.
 *
 * The badge carries the state and the stage next to it carries the position in
 * the pipeline.  Both are printed, so the state is never colour-only.  The
 * stage is only shown when it says something the status does not already say.
 */
export function DocumentStatusBadge({ status, stage }: DocumentStatusBadgeProps) {
  const showStage = Boolean(stage && stage.trim() !== status.trim())

  return (
    <span className="inline-flex items-center gap-2">
      <Badge tone={statusTone(status)} title={`processing_status: ${status}`} dot>
        <span className="font-mono text-caption">{status}</span>
      </Badge>
      {showStage ? (
        <>
          <span aria-hidden="true" className="h-3 w-px bg-line" />
          <span title="processing_stage" className="font-mono text-micro text-ink-subtle">
            {stage}
          </span>
        </>
      ) : null}
    </span>
  )
}