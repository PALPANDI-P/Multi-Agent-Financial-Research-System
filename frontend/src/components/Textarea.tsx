import type { TextareaHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  id: string
  hint?: string
  error?: string | null
  containerClassName?: string
}

export function Textarea({
  label,
  id,
  hint,
  error,
  className,
  containerClassName,
  required,
  ...rest
}: TextareaProps) {
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
      <textarea
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          'min-h-24 w-full rounded-control border border-line-strong bg-surface px-3 py-2.5 text-body text-ink',
          'transition-[border-color,box-shadow] duration-150 ease-out-soft',
          'placeholder:text-ink-subtle',
          'focus:border-brand-500 focus:ring-2 focus:ring-brand-500/25 focus:outline-none',
          'disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-ink-subtle',
          error && 'border-danger-600 focus:border-danger-600 focus:ring-danger-600/25',
          className,
        )}
        {...rest}
      />
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