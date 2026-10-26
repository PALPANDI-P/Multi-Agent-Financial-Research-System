import type { ReactNode } from 'react'
import { cn } from '../lib/cn'
import { FolderIcon } from './icons'

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
        'flex flex-col items-center justify-center gap-4 rounded-card border border-line bg-surface-muted/50 px-6 py-12 text-center',
        className,
      )}
    >
      <span
        className="inline-flex h-11 w-11 items-center justify-center rounded-panel border border-line bg-surface text-ink-subtle"
        aria-hidden="true"
      >
        {icon ?? <FolderIcon size={20} />}
      </span>
      <div className="max-w-md space-y-1.5">
        <p className="text-subtitle text-ink">{title}</p>
        {description ? <div className="text-small text-ink-muted">{description}</div> : null}
      </div>
      {action ? <div className="pt-1">{action}</div> : null}
    </div>
  )
}