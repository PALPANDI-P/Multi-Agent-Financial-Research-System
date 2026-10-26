import type { InputHTMLAttributes, Ref } from 'react'
import { cn } from '../lib/cn'
import { WarningIcon } from './icons'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Visible label text. Every input must have one. */
  label: string
  /** Stable id used to bind the label and the description/error nodes. */
  id: string
  hint?: string
  error?: string | null
  containerClassName?: string
  /** Optional ref of the underlying input, e.g. to move the focus. */
  inputRef?: Ref<HTMLInputElement>
}

export function Input({
  label,
  id,
  hint,
  error,
  className,
  containerClassName,
  inputRef,
  required,
  ...rest
}: InputProps) {
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
      <input
        id={id}
        ref={inputRef}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          'h-10 w-full rounded-control border border-line-strong bg-surface px-3 text-body text-ink',
          'transition-[border-color,box-shadow] duration-150 ease-out-soft',
          'placeholder:text-ink-subtle',
          'focus:border-brand-500 focus:ring-2 focus:ring-brand-500/25 focus:outline-none',
          'disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-ink-subtle',
          error &&
            'border-danger-600 focus:border-danger-600 focus:ring-danger-600/25',
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
        <p
          id={errorId}
          className="flex items-start gap-1.5 text-caption font-medium text-danger-700"
        >
          <WarningIcon size={13} className="mt-px shrink-0" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  )
}