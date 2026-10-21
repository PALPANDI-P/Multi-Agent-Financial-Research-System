import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export type BadgeTone = 'neutral' | 'brand' | 'info' | 'success' | 'warning' | 'danger'

export interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
  className?: string
  title?: string
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-muted text-ink-muted border-line-strong',
  brand: 'bg-brand-50 text-brand-700 border-brand-200',
  info: 'bg-info-50 text-info-700 border-info-200',
  success: 'bg-success-50 text-success-700 border-success-100',
  warning: 'bg-warning-50 text-warning-700 border-warning-100',
  danger: 'bg-danger-50 text-danger-700 border-danger-200',
}

export function Badge({ tone = 'neutral', children, className, title }: BadgeProps) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 rounded-pill border px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
