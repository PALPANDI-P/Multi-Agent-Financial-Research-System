import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

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
  info: 'bg-info-50 border-info-200 text-info-700',
  success: 'bg-success-50 border-success-100 text-success-700',
  warning: 'bg-warning-50 border-warning-100 text-warning-700',
  danger: 'bg-danger-50 border-danger-200 text-danger-700',
}

const TONE_ICON: Record<AlertTone, string> = {
  info: 'text-info-600',
  success: 'text-success-600',
  warning: 'text-warning-600',
  danger: 'text-danger-600',
}

export function Alert({ tone = 'info', title, children, code, className, action }: AlertProps) {
  const isDanger = tone === 'danger'

  return (
    <div
      role={isDanger ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-3 rounded-card border px-4 py-3 text-sm',
        TONE_CLASSES[tone],
        className,
      )}
    >
      <svg
        className={cn('mt-0.5 h-4 w-4 shrink-0', TONE_ICON[tone])}
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        {isDanger ? (
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm1-11a1 1 0 1 0-2 0v4a1 1 0 1 0 2 0V7Zm-1 7.25a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z"
            clipRule="evenodd"
          />
        ) : (
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-11.5a.75.75 0 0 0-1.5 0v4.5a.75.75 0 0 0 1.5 0v-4.5ZM10 14a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z"
            clipRule="evenodd"
          />
        )}
      </svg>
      <div className="min-w-0 flex-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={cn(title ? 'mt-0.5' : undefined)}>{children}</div> : null}
        {code ? (
          <p className="mt-1 font-mono text-xs opacity-80">
            Error code: <span className="font-semibold">{code}</span>
          </p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

