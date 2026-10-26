import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface CardProps {
  children: ReactNode
  className?: string
  /** Lifts the card by two pixels on hover - use it for clickable cards. */
  interactive?: boolean
}

export function Card({ children, className, interactive = false }: CardProps) {
  return (
    <section
      className={cn(
        'rounded-card border border-line bg-surface shadow-card',
        interactive && 'card-interactive',
        className,
      )}
    >
      {children}
    </section>
  )
}

export interface CardHeaderProps {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

export function CardHeader({ title, description, actions, className }: CardHeaderProps) {
  return (
    <header
      className={cn(
        'flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6 sm:px-6 sm:py-5',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-subtitle text-ink">{title}</h2>
        {description ? (
          <div className="mt-1 max-w-prose text-small text-ink-muted">{description}</div>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}

export function CardBody({ children, className }: CardProps) {
  return <div className={cn('px-5 py-5 sm:px-6', className)}>{children}</div>
}

export function CardFooter({ children, className }: CardProps) {
  return (
    <footer
      className={cn(
        'flex flex-wrap items-center gap-2 border-t border-line bg-surface-muted/50 px-5 py-3.5 sm:px-6',
        className,
      )}
    >
      {children}
    </footer>
  )
}