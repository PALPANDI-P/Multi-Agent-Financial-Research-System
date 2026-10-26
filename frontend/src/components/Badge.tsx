import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

/**
 * Tones of the badge.
 *
 * The first six are the generic semantic tones.  The remaining ones are the
 * eight states of the ingestion pipeline: every state owns a distinguishable
 * colour and is *always* rendered together with the raw status text, so the
 * badge is never colour-only.
 */
export type BadgeTone =
  | 'neutral'
  | 'brand'
  | 'info'
  | 'success'
  | 'warning'
  | 'danger'
  | 'queued'
  | 'validating'
  | 'extracting'
  | 'chunking'
  | 'embedding'
  | 'indexing'
  | 'completed'
  | 'failed'

export interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
  className?: string
  title?: string
  /** Prints a small dot in the tone colour in front of the label. */
  dot?: boolean
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'border-line bg-surface-muted text-ink-muted',
  brand: 'border-brand-200 bg-brand-50 text-brand-800',
  info: 'border-info-200 bg-info-50 text-info-700',
  success: 'border-success-200 bg-success-50 text-success-700',
  warning: 'border-warning-200 bg-warning-50 text-warning-700',
  danger: 'border-danger-200 bg-danger-50 text-danger-700',
  queued: 'border-status-queued-line bg-status-queued-soft text-status-queued',
  validating: 'border-status-validating-line bg-status-validating-soft text-status-validating',
  extracting: 'border-status-extracting-line bg-status-extracting-soft text-status-extracting',
  chunking: 'border-status-chunking-line bg-status-chunking-soft text-status-chunking',
  embedding: 'border-status-embedding-line bg-status-embedding-soft text-status-embedding',
  indexing: 'border-status-indexing-line bg-status-indexing-soft text-status-indexing',
  completed: 'border-status-completed-line bg-status-completed-soft text-status-completed',
  failed: 'border-status-failed-line bg-status-failed-soft text-status-failed',
}

export function Badge({ tone = 'neutral', children, className, title, dot = false }: BadgeProps) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-pill border px-2 py-0.5 text-caption font-medium whitespace-nowrap',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {dot ? (
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 shrink-0 rounded-pill bg-current opacity-80"
        />
      ) : null}
      {children}
    </span>
  )
}