import { cn } from '../lib/cn'
import { SpinnerIcon } from './icons'

export interface SpinnerProps {
  className?: string
  label?: string
  /** Hide the visible label but keep it for screen readers. */
  hideLabel?: boolean
}

export function Spinner({ className, label = 'Loading', hideLabel = false }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn('inline-flex items-center gap-2 text-small text-ink-muted', className)}
    >
      <SpinnerIcon size={18} className="shrink-0 animate-spin text-brand-600" />
      <span className={cn(hideLabel && 'sr-only')}>{label}</span>
    </span>
  )
}