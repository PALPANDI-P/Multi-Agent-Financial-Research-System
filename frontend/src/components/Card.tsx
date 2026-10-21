import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface CardProps {
  children: ReactNode
  className?: string
}

export function Card({ children, className }: CardProps) {
  return (
    <section
      className={cn(
        'rounded-card border border-line bg-surface shadow-[0_1px_2px_rgba(16,24,40,0.04)]',
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
        'flex flex-col gap-3 border-b border-line px-4 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4 sm:px-5',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {description ? <p className="mt-1 text-sm text-ink-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}

export function CardBody({ children, className }: CardProps) {
  return <div className={cn('px-4 py-4 sm:px-5', className)}>{children}</div>
}

export function CardFooter({ children, className }: CardProps) {
  return (
    <footer
      className={cn(
        'flex flex-wrap items-center gap-2 border-t border-line px-4 py-3 sm:px-5',
        className,
      )}
    >
      {children}
    </footer>
  )
}
