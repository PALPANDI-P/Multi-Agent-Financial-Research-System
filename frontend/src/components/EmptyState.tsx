import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface EmptyStateProps {
  title: string
  description?: ReactNode
  action?: ReactNode
  icon?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-card border border-dashed border-line-strong bg-surface px-6 py-10 text-center',
        className,
      )}
    >
      <div className="text-ink-subtle" aria-hidden="true">
        {icon ?? (
          <svg className="h-8 w-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path
              d="M3.75 6.75A1.5 1.5 0 0 1 5.25 5.25h4.19l1.5 1.88h7.81a1.5 1.5 0 0 1 1.5 1.5v9.62a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5V6.75Z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-ink">{title}</p>
        {description ? <div className="text-sm text-ink-muted">{description}</div> : null}
      </div>
      {action ? <div className="pt-1">{action}</div> : null}
    </div>
  )
}
