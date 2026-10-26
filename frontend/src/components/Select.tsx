import type { SelectHTMLAttributes } from 'react'
import { cn } from '../lib/cn'
import { ChevronDownIcon } from './icons'

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
      <label htmlFor={id} className="text-small font-medium text-ink">
        {label}
        {required ? (
          <span className="ml-1 text-danger-600" aria-hidden="true">
            *
          </span>
        ) : null}
        {required ? <span className="sr-only"> (required)</span> : null}
      </label>
      <div className="relative">
        <select
          id={id}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            'h-10 w-full appearance-none rounded-control border border-line-strong bg-surface py-0 pr-9 pl-3 text-body text-ink',
            'transition-[border-color,box-shadow] duration-150 ease-out-soft',
            'focus:border-brand-500 focus:ring-2 focus:ring-brand-500/25 focus:outline-none',
            'disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-ink-subtle',
            error && 'border-danger-600 focus:border-danger-600 focus:ring-danger-600/25',
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
        <ChevronDownIcon
          size={16}
          className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-ink-subtle"
        />
      </div>
      {hint ? (
        <p id={hintId} className="text-caption text-ink-subtle">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-caption font-medium text-danger-700">
          {error}
        </p>
      ) : null}
    </div>
  )
}