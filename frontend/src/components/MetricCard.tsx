import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface MetricCardProps {
  label: string
  value: ReactNode
  /** Explains what the number is measured over. */
  hint?: ReactNode
  icon?: ReactNode
  className?: string
  /** Overrides the type of the value, e.g. for a figure that is a name. */
  valueClassName?: string
  /** The size of the figure.  The row of the dashboard uses `lg`. */
  valueSize?: 'sm' | 'md' | 'lg'
}

const VALUE_SIZE_CLASSES: Record<NonNullable<MetricCardProps['valueSize']>, string> = {
  sm: 'text-subtitle',
  md: 'text-title',
  lg: 'text-headline',
}

/**
 * A single number of the workspace.  The value is always rendered by the
 * caller - the component never invents one.
 */
export function MetricCard({
  label,
  value,
  hint,
  icon,
  className,
  valueClassName,
  valueSize = 'md',
}: MetricCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-card border border-line bg-surface p-4 shadow-card sm:p-5',
        className,
      )}
    >
      <div className="flex items-center gap-2">
        {icon ? (
          <span
            aria-hidden="true"
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-xs bg-surface-muted text-ink-subtle"
          >
            {icon}
          </span>
        ) : null}
        <p className="text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
          {label}
        </p>
      </div>
      <p
        className={cn(
          'text-ink tabular-nums',
          VALUE_SIZE_CLASSES[valueSize],
          valueClassName,
        )}
      >
        {value}
      </p>
      {hint ? <p className="mt-auto text-caption text-ink-subtle">{hint}</p> : null}
    </div>
  )
}