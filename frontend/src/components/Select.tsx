import type { SelectHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  id: string
  options: SelectOption[]
  hint?: string
  error?: string | null
  containerClassName?: string
}

export function Select({
  label,
  id,
  options,
  hint,
  error,
  className,
  containerClassName,
  required,
  ...rest
}: SelectProps) {
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('flex flex-col gap-1.5', containerClassName)}>
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {label}
        {required ? (
          <span className="ml-1 text-danger-600" aria-hidden="true">
            *
          </span>
        ) : null}
        {required ? <span className="sr-only"> (required)</span> : null}
      </label>
      <select
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          'h-10 w-full rounded-control border border-line-strong bg-surface px-3 text-sm text-ink',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:border-brand-600',
          'disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-ink-subtle',
          error && 'border-danger-600 focus-visible:ring-danger-600',
          className,
        )}
        {...rest}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint ? (
        <p id={hintId} className="text-xs text-ink-subtle">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs font-medium text-danger-700">
          {error}
        </p>
      ) : null}
    </div>
  )
}
