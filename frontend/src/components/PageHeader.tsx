import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  /** Small label above the title, e.g. the section a page belongs to. */
  eyebrow?: ReactNode
  actions?: ReactNode
  className?: string
}

/**
 * The heading block of a page: an optional eyebrow, the page title, a short
 * description and the primary actions on the right.
 */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        'flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between sm:gap-8',
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow ? (
          <p className="flex items-center gap-2 text-micro font-semibold tracking-[0.14em] text-brand-700 uppercase">
            <span aria-hidden="true" className="h-px w-5 bg-brand-300" />
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mt-2.5 text-headline text-ink">{title}</h1>
        {description ? (
          <div className="mt-2.5 max-w-prose text-body text-ink-muted">{description}</div>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </header>
  )
}