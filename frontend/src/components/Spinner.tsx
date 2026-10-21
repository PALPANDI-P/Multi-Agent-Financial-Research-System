import { cn } from '../lib/cn'

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
      className={cn('inline-flex items-center gap-2 text-sm text-ink-muted', className)}
    >
      <svg
        className="h-4 w-4 shrink-0 animate-spin text-brand-600"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle
          className="opacity-20"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-90"
          fill="currentColor"
          d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
        />
      </svg>
      <span className={cn(hideLabel && 'sr-only')}>{label}</span>
    </span>
  )
}
