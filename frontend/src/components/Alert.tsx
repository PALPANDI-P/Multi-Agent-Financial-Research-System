import type { ReactNode } from 'react'
import { cn } from '../lib/cn'
import { CheckIcon, InfoIcon, WarningIcon } from './icons'

export type AlertTone = 'info' | 'success' | 'warning' | 'danger'

export interface AlertProps {
  tone?: AlertTone
  title?: ReactNode
  children?: ReactNode
  /** Error code from the API envelope, rendered next to the message. */
  code?: string | null
  className?: string
  action?: ReactNode
}

const TONE_CLASSES: Record<AlertTone, string> = {
  info: 'border-info-200 bg-info-50/70',
  success: 'border-success-200 bg-success-50/70',
  warning: 'border-warning-200 bg-warning-50/70',
  danger: 'border-danger-200 bg-danger-50/70',
}

const TONE_ICON_CLASSES: Record<AlertTone, string> = {
  info: 'text-info-600',
  success: 'text-success-600',
  warning: 'text-warning-600',
  danger: 'text-danger-600',
}

const TONE_RULE_CLASSES: Record<AlertTone, string> = {
  info: 'bg-info-600',
  success: 'bg-success-600',
  warning: 'bg-warning-600',
  danger: 'bg-danger-600',
}

export function Alert({ tone = 'info', title, children, code, className, action }: AlertProps) {
  const isDanger = tone === 'danger'

  return (
    <div
      role={isDanger ? 'alert' : 'status'}
      className={cn(
        'relative flex items-start gap-3 overflow-hidden rounded-card border py-3.5 pr-4 pl-5 text-small',
        TONE_CLASSES[tone],
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn('absolute inset-y-0 left-0 w-[3px]', TONE_RULE_CLASSES[tone])}
      />

      <span className={cn('mt-0.5 shrink-0', TONE_ICON_CLASSES[tone])} aria-hidden="true">
        {tone === 'danger' || tone === 'warning' ? (
          <WarningIcon size={18} />
        ) : tone === 'success' ? (
          <CheckIcon size={18} />
        ) : (
          <InfoIcon size={18} />
        )}
      </span>

      <div className="min-w-0 flex-1">
        {title ? <p className="font-semibold text-ink">{title}</p> : null}
        {children ? (
          <div className={cn('text-ink-muted', title ? 'mt-0.5' : undefined)}>{children}</div>
        ) : null}
        {code ? (
          <p className="mt-1.5 font-mono text-caption text-ink-subtle">
            error code <span className="font-semibold text-ink-muted">{code}</span>
          </p>
        ) : null}
      </div>

      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}